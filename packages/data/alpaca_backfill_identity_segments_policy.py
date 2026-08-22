from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity_segments import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
    AlpacaBackfillIdentitySegmentBuilder as BaseIdentitySegmentBuilder,
    _observed_map,
    _safe_edge_rows,
    _text,
    build_identity_segments,
)
from packages.data.alpaca_backfill_identity_policy import (
    ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
)


ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION = (
    "historical-backfill-identity-segments-v2-cusip-ambiguous-node-quarantine"
)
CUSIP_AMBIGUITY_REASON = "SHARED_RENAME_NODE_HAS_MULTIPLE_CUSIPS"


@dataclass(frozen=True, slots=True)
class CusipNodePartition:
    eligible_edges: list[dict[str, object]]
    quarantined_edges: list[dict[str, object]]
    ambiguous_symbols: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class AlpacaBackfillIdentitySegmentPolicyReport:
    contract_version: str
    parent_segment_contract_version: str
    identity_policy_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    observed_symbols: int
    safe_candidate_rows: int
    input_unique_safe_edges: int
    duplicate_safe_candidate_rows: int
    quarantined_safe_candidate_rows: int
    quarantined_unique_safe_edges: int
    identity_eligible_safe_edges: int
    cusip_ambiguous_symbols: int
    identity_chains: int
    identity_segments: int
    singleton_chains: int
    multi_symbol_chains: int
    max_chain_length: int
    expected_chain_count: int
    edge_component_accounting: bool
    chain_coverage_exact: bool
    eligible_safe_edges_consumed_exact: bool
    quarantine_accounting_exact: bool
    safe_edge_path: str
    quarantined_safe_edge_path: str
    ambiguous_symbol_path: str
    chain_path: str
    segment_path: str
    report_path: str


def partition_safe_edges_by_cusip_node(
    edges: list[dict[str, object]],
) -> CusipNodePartition:
    """Quarantine safe edges that touch a literal symbol evidenced under >1 CUSIP.

    Gate 4-B validates each rename transition independently. Gate 4-C must additionally
    ensure that transitive chaining does not assign one whole observed ticker interval to
    two different security identifiers. If a shared rename node appears on incident safe
    edges with different CUSIPs, ATLAS has no retained evidence locating the intra-symbol
    identity boundary. All incident edges are therefore quarantined from chain construction.
    """

    symbol_cusips: dict[str, set[str]] = {}
    for edge in edges:
        source = _text(edge.get("old_symbol"))
        target = _text(edge.get("new_symbol"))
        cusip = _text(edge.get("cusip"))
        if source is None or target is None or cusip is None:
            raise RuntimeError("Gate 4-C candidate safe edge lacks exact symbol/CUSIP evidence")
        symbol_cusips.setdefault(source, set()).add(cusip)
        symbol_cusips.setdefault(target, set()).add(cusip)

    ambiguous = {
        symbol: tuple(sorted(cusips))
        for symbol, cusips in symbol_cusips.items()
        if len(cusips) > 1
    }

    eligible: list[dict[str, object]] = []
    quarantined: list[dict[str, object]] = []
    ambiguous_set = set(ambiguous)

    for edge in edges:
        source = str(edge["old_symbol"])
        target = str(edge["new_symbol"])
        touched = sorted({source, target} & ambiguous_set)
        if not touched:
            eligible.append(dict(edge))
            continue

        revised = dict(edge)
        revised.update(
            {
                "quarantine_reason": CUSIP_AMBIGUITY_REASON,
                "ambiguous_endpoint_symbols_json": json.dumps(touched),
                "ambiguous_endpoint_cusips_json": json.dumps(
                    {symbol: list(ambiguous[symbol]) for symbol in touched},
                    sort_keys=True,
                ),
            }
        )
        quarantined.append(revised)

    return CusipNodePartition(
        eligible_edges=eligible,
        quarantined_edges=quarantined,
        ambiguous_symbols=ambiguous,
    )


def quarantine_ambiguous_safe_rename_rows(
    rename_rows: list[dict[str, object]],
    ambiguous_symbols: set[str],
) -> list[dict[str, object]]:
    """Remove graph-level ambiguous edges from automatic continuity without deleting evidence."""

    result: list[dict[str, object]] = []
    for row in rename_rows:
        revised = dict(row)
        source = _text(row.get("old_symbol"))
        target = _text(row.get("new_symbol"))
        status = _text(row.get("status"))
        if (
            status == "SAFE_STITCH_CANDIDATE"
            and bool(row.get("safe_to_stitch"))
            and ((source in ambiguous_symbols) or (target in ambiguous_symbols))
        ):
            revised["status"] = "GRAPH_QUARANTINED"
            revised["safe_to_stitch"] = False
            revised["graph_quarantine_reason"] = CUSIP_AMBIGUITY_REASON
        result.append(revised)
    return result


def _annotate_ambiguity(
    chain_rows: list[dict[str, object]],
    segment_rows: list[dict[str, object]],
    ambiguous_symbols: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    revised_chains: list[dict[str, object]] = []
    for row in chain_rows:
        revised = dict(row)
        symbol = _text(row.get("first_symbol"))
        ambiguous = int(row.get("chain_length", 0)) == 1 and symbol in ambiguous_symbols
        revised["identity_ambiguous"] = ambiguous
        revised["identity_ambiguity_reason"] = CUSIP_AMBIGUITY_REASON if ambiguous else None
        if ambiguous:
            revised["continuity_basis"] = "OBSERVED_LITERAL_CUSIP_AMBIGUOUS"
            revised["cusip"] = None
        revised_chains.append(revised)

    revised_segments: list[dict[str, object]] = []
    for row in segment_rows:
        revised = dict(row)
        symbol = _text(row.get("symbol"))
        ambiguous = symbol in ambiguous_symbols
        revised["identity_ambiguous"] = ambiguous
        revised["identity_ambiguity_reason"] = CUSIP_AMBIGUITY_REASON if ambiguous else None
        if ambiguous:
            revised["continuity_basis"] = "OBSERVED_LITERAL_CUSIP_AMBIGUOUS"
            revised["cusip"] = None
        revised_segments.append(revised)

    return revised_chains, revised_segments


class AlpacaBackfillIdentitySegmentPolicyBuilder:
    """Gate 4-C v2 chain builder with graph-level multi-CUSIP node quarantine."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.base = BaseIdentitySegmentBuilder(settings)
        self.quarantined_safe_edge_path = (
            self.base.identity_root / "quarantined_safe_rename_edges.parquet"
        )
        self.ambiguous_symbol_path = (
            self.base.identity_root / "identity_ambiguous_symbols.parquet"
        )

    def run(self) -> AlpacaBackfillIdentitySegmentPolicyReport:
        _acquisition, identity = self.base._load_parent_reports()
        observed_rows = self.base._read_rows(
            self.base.observed_summary_path,
            "symbol",
            where="observed = TRUE",
        )
        rename_rows = self.base._read_rows(
            self.base.rename_candidate_path,
            "event_date NULLS LAST, old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
        )

        observed = _observed_map(observed_rows)
        candidate_edges, safe_candidate_rows, duplicate_safe_rows = _safe_edge_rows(
            observed,
            rename_rows,
        )
        if safe_candidate_rows != int(identity.get("safe_stitch_candidates", -1)):
            raise RuntimeError(
                "Gate 4-C input safe candidate row count does not match Gate 4-B report: "
                f"rows={safe_candidate_rows} report={identity.get('safe_stitch_candidates')}"
            )

        partition = partition_safe_edges_by_cusip_node(candidate_edges)
        ambiguous_set = set(partition.ambiguous_symbols)
        filtered_renames = quarantine_ambiguous_safe_rename_rows(rename_rows, ambiguous_set)
        result = build_identity_segments(observed_rows, filtered_renames)

        eligible_ids = {str(row["safe_edge_id"]) for row in partition.eligible_edges}
        built_ids = {str(row["safe_edge_id"]) for row in result.edge_rows}
        if built_ids != eligible_ids:
            raise RuntimeError("Gate 4-C eligible edge set changed during chain construction")

        quarantined_candidate_rows = sum(
            int(row.get("evidence_event_count", 0)) for row in partition.quarantined_edges
        )
        if safe_candidate_rows != result.safe_candidate_rows + quarantined_candidate_rows:
            raise RuntimeError("Gate 4-C safe candidate row quarantine accounting mismatch")

        chain_rows, segment_rows = _annotate_ambiguity(
            result.chain_rows,
            result.segment_rows,
            ambiguous_set,
        )

        ambiguous_rows = [
            {
                "symbol": symbol,
                "cusip_count": len(cusips),
                "cusips_json": json.dumps(list(cusips)),
                "identity_ambiguity_reason": CUSIP_AMBIGUITY_REASON,
                "automatic_continuity_forbidden": True,
            }
            for symbol, cusips in sorted(partition.ambiguous_symbols.items())
        ]

        self.base._write_parquet(
            self.base.safe_edge_path,
            result.edge_rows,
            "old_symbol, new_symbol, safe_edge_id",
        )
        self.base._write_parquet(
            self.quarantined_safe_edge_path,
            partition.quarantined_edges,
            "old_symbol, new_symbol, safe_edge_id",
        )
        self.base._write_parquet(
            self.ambiguous_symbol_path,
            ambiguous_rows,
            "symbol",
        )
        self.base._write_parquet(
            self.base.chain_path,
            chain_rows,
            "first_symbol, identity_chain_id",
        )
        self.base._write_parquet(
            self.base.segment_path,
            segment_rows,
            "identity_chain_id, chain_position, symbol",
        )

        observed_count = len(observed_rows)
        eligible_edge_count = len(result.edge_rows)
        input_unique_edges = len(candidate_edges)
        quarantined_edge_count = len(partition.quarantined_edges)
        expected_chains = observed_count - eligible_edge_count
        chain_count = len(chain_rows)
        segment_count = len(segment_rows)
        singleton_chains = sum(1 for row in chain_rows if int(row["chain_length"]) == 1)
        multi_symbol_chains = chain_count - singleton_chains
        max_chain_length = max((int(row["chain_length"]) for row in chain_rows), default=0)
        consumed_edges = sum(int(row["safe_edge_count"]) for row in chain_rows)

        report = AlpacaBackfillIdentitySegmentPolicyReport(
            contract_version=ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
            parent_segment_contract_version=ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
            identity_policy_contract_version=ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            observed_symbols=observed_count,
            safe_candidate_rows=safe_candidate_rows,
            input_unique_safe_edges=input_unique_edges,
            duplicate_safe_candidate_rows=duplicate_safe_rows,
            quarantined_safe_candidate_rows=quarantined_candidate_rows,
            quarantined_unique_safe_edges=quarantined_edge_count,
            identity_eligible_safe_edges=eligible_edge_count,
            cusip_ambiguous_symbols=len(ambiguous_rows),
            identity_chains=chain_count,
            identity_segments=segment_count,
            singleton_chains=singleton_chains,
            multi_symbol_chains=multi_symbol_chains,
            max_chain_length=max_chain_length,
            expected_chain_count=expected_chains,
            edge_component_accounting=chain_count == expected_chains,
            chain_coverage_exact=segment_count == observed_count,
            eligible_safe_edges_consumed_exact=eligible_edge_count == consumed_edges,
            quarantine_accounting_exact=(
                input_unique_edges == eligible_edge_count + quarantined_edge_count
                and safe_candidate_rows
                == result.safe_candidate_rows + quarantined_candidate_rows
            ),
            safe_edge_path=str(self.base.safe_edge_path),
            quarantined_safe_edge_path=str(self.quarantined_safe_edge_path),
            ambiguous_symbol_path=str(self.ambiguous_symbol_path),
            chain_path=str(self.base.chain_path),
            segment_path=str(self.base.segment_path),
            report_path=str(self.base.report_path),
        )

        if not (
            report.edge_component_accounting
            and report.chain_coverage_exact
            and report.eligible_safe_edges_consumed_exact
            and report.quarantine_accounting_exact
        ):
            raise RuntimeError("Gate 4-C v2 identity-chain validation invariant failed")

        atomic_write_text(
            self.base.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
