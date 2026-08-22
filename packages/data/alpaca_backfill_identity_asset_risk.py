from __future__ import annotations

import gzip
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_identity_segments import AlpacaBackfillIdentitySegmentBuilder
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore


ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION = (
    "historical-backfill-identity-asset-risk-v1-current-uuid-multiplicity-reference-only"
)
ASSET_ID_MULTIPLICITY_REFERENCE = "ASSET_ID_MULTIPLICITY_REFERENCE"
ASSET_ID_REFERENCE_POLICY = "CURRENT_ASSET_STATE_DISCOVERY_REFERENCE_ONLY"
ASSET_ID_HISTORICAL_EFFECT = "NO_RETROACTIVE_IDENTITY_SEGMENTATION"
ASSET_PARTITIONS = {"assets_active", "assets_inactive"}


@dataclass(frozen=True, slots=True)
class AssetRiskAnalysis:
    reference_rows: list[dict[str, object]]
    raw_asset_rows: int
    raw_exact_symbols: int
    distinct_symbol_asset_id_pairs: int
    symbols_with_multiple_asset_ids: int
    observed_symbols_with_multiple_asset_ids: int
    reuse_touching_eligible_edge: int
    reuse_touching_quarantined_edge: int
    reuse_in_multi_symbol_chain: int


@dataclass(frozen=True, slots=True)
class AlpacaBackfillIdentityAssetRiskReport:
    contract_version: str
    parent_segment_policy_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    asset_state_role: str
    historical_identity_effect: str
    raw_asset_payloads: int
    raw_asset_rows: int
    raw_exact_symbols: int
    distinct_symbol_asset_id_pairs: int
    symbols_with_multiple_asset_ids: int
    observed_symbols_with_multiple_asset_ids: int
    reuse_touching_eligible_edge: int
    reuse_touching_quarantined_edge: int
    reuse_in_multi_symbol_chain: int
    reference_rows: int
    segment_reference_annotations: int
    chain_reference_annotations: int
    parent_identity_chains: int
    parent_identity_segments: int
    resulting_identity_chains: int
    resulting_identity_segments: int
    historical_chain_structure_unchanged: bool
    reference_policy_is_non_segmenting: bool
    reference_artifact_path: str
    chain_path: str
    segment_path: str
    report_path: str


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def asset_records_from_payload(payload: Any, partition: str) -> list[dict[str, object]]:
    if partition not in ASSET_PARTITIONS:
        raise ValueError(f"unsupported Alpaca asset partition: {partition}")
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected Alpaca asset payload shape for {partition}")

    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = _clean_text(item.get("symbol"))
        asset_id = _clean_text(item.get("id"))
        if symbol is None or asset_id is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "asset_id": asset_id,
                "partition": partition,
                "status": _clean_text(item.get("status")),
                "exchange": _clean_text(item.get("exchange")),
                "asset_class": _clean_text(item.get("class")),
                "name": _clean_text(item.get("name")),
                "tradable": item.get("tradable"),
            }
        )
    return rows


def analyze_asset_id_reference_risk(
    asset_rows: list[dict[str, object]],
    observed_symbols: set[str],
    eligible_edges: list[dict[str, object]],
    quarantined_edges: list[dict[str, object]],
    segment_rows: list[dict[str, object]],
) -> AssetRiskAnalysis:
    by_symbol: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for row in asset_rows:
        symbol = _clean_text(row.get("symbol"))
        asset_id = _clean_text(row.get("asset_id"))
        if symbol is None or asset_id is None:
            continue
        by_symbol[symbol].setdefault(asset_id, dict(row))

    reused = {symbol: records for symbol, records in by_symbol.items() if len(records) > 1}
    observed_reused = {
        symbol: records for symbol, records in reused.items() if symbol in observed_symbols
    }

    eligible_touch: set[str] = set()
    for edge in eligible_edges:
        for field in ("old_symbol", "new_symbol"):
            symbol = _clean_text(edge.get(field))
            if symbol is not None:
                eligible_touch.add(symbol)

    quarantine_touch: set[str] = set()
    for edge in quarantined_edges:
        for field in ("old_symbol", "new_symbol"):
            symbol = _clean_text(edge.get(field))
            if symbol is not None:
                quarantine_touch.add(symbol)

    segment_by_symbol = {
        str(row["symbol"]): row
        for row in segment_rows
        if _clean_text(row.get("symbol")) is not None
    }

    reuse_touching_eligible = sorted(set(observed_reused) & eligible_touch)
    reuse_touching_quarantine = sorted(set(observed_reused) & quarantine_touch)
    reuse_multi_chain = sorted(
        symbol
        for symbol in observed_reused
        if int(segment_by_symbol.get(symbol, {}).get("chain_length", 1)) > 1
    )

    # Current active/inactive asset state is reference-only. If it intersects a proven
    # historical continuity edge or a multi-symbol chain, fail closed for manual review
    # rather than projecting current UUID state backward into the 2016-2021 period.
    if reuse_touching_eligible:
        raise RuntimeError(
            "Gate 4-D current Alpaca asset-ID multiplicity touches identity-eligible rename "
            f"continuity: {reuse_touching_eligible[:10]}"
        )
    if reuse_touching_quarantine:
        raise RuntimeError(
            "Gate 4-D current Alpaca asset-ID multiplicity touches existing graph quarantine: "
            f"{reuse_touching_quarantine[:10]}"
        )
    if reuse_multi_chain:
        raise RuntimeError(
            "Gate 4-D current Alpaca asset-ID multiplicity appears inside multi-symbol chain: "
            f"{reuse_multi_chain[:10]}"
        )

    reference_rows: list[dict[str, object]] = []
    for symbol in sorted(observed_reused):
        records = observed_reused[symbol]
        values = sorted(
            records.values(),
            key=lambda row: (str(row.get("partition")), str(row.get("asset_id"))),
        )
        reference_rows.append(
            {
                "symbol": symbol,
                "asset_id_count": len(records),
                "asset_ids_json": json.dumps(sorted(records)),
                "asset_records_json": json.dumps(values, sort_keys=True),
                "risk_classification": ASSET_ID_MULTIPLICITY_REFERENCE,
                "asset_state_role": ASSET_ID_REFERENCE_POLICY,
                "historical_identity_effect": ASSET_ID_HISTORICAL_EFFECT,
                "automatic_continuity_forbidden": False,
                "historical_identity_ambiguous_from_uuid_alone": False,
            }
        )

    return AssetRiskAnalysis(
        reference_rows=reference_rows,
        raw_asset_rows=len(asset_rows),
        raw_exact_symbols=len(by_symbol),
        distinct_symbol_asset_id_pairs=sum(len(records) for records in by_symbol.values()),
        symbols_with_multiple_asset_ids=len(reused),
        observed_symbols_with_multiple_asset_ids=len(observed_reused),
        reuse_touching_eligible_edge=len(reuse_touching_eligible),
        reuse_touching_quarantined_edge=len(reuse_touching_quarantine),
        reuse_in_multi_symbol_chain=len(reuse_multi_chain),
    )


def annotate_asset_id_reference(
    rows: list[dict[str, object]],
    reference_by_symbol: dict[str, dict[str, object]],
    *,
    symbol_field: str,
) -> tuple[list[dict[str, object]], int]:
    revised_rows: list[dict[str, object]] = []
    annotations = 0
    for row in rows:
        revised = dict(row)
        symbol = _clean_text(row.get(symbol_field))
        reference = reference_by_symbol.get(symbol or "")
        flagged = reference is not None
        revised["asset_id_multiplicity_reference"] = flagged
        revised["asset_id_reference_count"] = int(reference["asset_id_count"]) if reference else 0
        revised["asset_id_reference_ids_json"] = reference["asset_ids_json"] if reference else None
        revised["asset_id_reference_policy"] = ASSET_ID_REFERENCE_POLICY if flagged else None
        if flagged:
            annotations += 1
        revised_rows.append(revised)
    return revised_rows, annotations


class AlpacaBackfillIdentityAssetRiskBuilder:
    """Gate 4-D current asset-UUID multiplicity reference layer; no provider fetch."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.base = AlpacaBackfillIdentitySegmentBuilder(settings)
        self.raw_store = AlpacaRawPayloadStore(settings)
        self.parent_report_path = self.base.report_path
        self.quarantined_edge_path = self.base.identity_root / "quarantined_safe_rename_edges.parquet"
        self.reference_path = self.base.identity_root / "asset_id_multiplicity_reference.parquet"
        self.report_path = self.base.identity_root / "identity_asset_risk_report.json"

    def _load_raw_asset_rows(self) -> tuple[list[dict[str, object]], int]:
        rows: list[dict[str, object]] = []
        retained_payloads = 0
        seen_partitions: set[str] = set()
        root = self.raw_store.root / "v2"
        for meta_path in root.glob("*/*.meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("category") != "discovery":
                continue
            partition = str(meta.get("partition") or "")
            if partition not in ASSET_PARTITIONS:
                continue
            payload_path = Path(str(meta.get("payload_path") or ""))
            if not payload_path.is_file():
                raise RuntimeError(f"Gate 4-D retained asset payload is missing: {payload_path}")
            with gzip.open(payload_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            rows.extend(asset_records_from_payload(payload, partition))
            retained_payloads += 1
            seen_partitions.add(partition)
        if seen_partitions != ASSET_PARTITIONS:
            raise RuntimeError(
                "Gate 4-D requires retained active and inactive asset discovery evidence"
            )
        return rows, retained_payloads

    def run(self) -> AlpacaBackfillIdentityAssetRiskReport:
        if not self.parent_report_path.is_file():
            raise RuntimeError("Gate 4-D requires the Gate 4-C identity segment report")
        parent = json.loads(self.parent_report_path.read_text(encoding="utf-8"))
        if parent.get("contract_version") != ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION:
            raise RuntimeError("Gate 4-D requires the Gate 4-C v2 CUSIP-node quarantine contract")
        if parent.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 4-D parent report does not preserve canonical safety")

        observed_rows = self.base._read_rows(
            self.base.observed_summary_path,
            "symbol",
            where="observed = TRUE",
        )
        observed_symbols = {str(row["symbol"]) for row in observed_rows}
        eligible_edges = self.base._read_rows(self.base.safe_edge_path, "old_symbol, new_symbol")
        quarantined_edges = self.base._read_rows(
            self.quarantined_edge_path,
            "old_symbol, new_symbol",
        )
        segment_rows = self.base._read_rows(
            self.base.segment_path,
            "identity_chain_id, chain_position, symbol",
        )
        chain_rows = self.base._read_rows(
            self.base.chain_path,
            "first_symbol, identity_chain_id",
        )
        asset_rows, retained_payloads = self._load_raw_asset_rows()

        analysis = analyze_asset_id_reference_risk(
            asset_rows,
            observed_symbols,
            eligible_edges,
            quarantined_edges,
            segment_rows,
        )
        reference_by_symbol = {str(row["symbol"]): row for row in analysis.reference_rows}
        segment_by_symbol = {str(row["symbol"]): row for row in segment_rows}

        annotated_segments, segment_annotations = annotate_asset_id_reference(
            segment_rows,
            reference_by_symbol,
            symbol_field="symbol",
        )
        singleton_reference = {
            symbol: row
            for symbol, row in reference_by_symbol.items()
            if int(segment_by_symbol[symbol]["chain_length"]) == 1
        }
        annotated_chains, chain_annotations = annotate_asset_id_reference(
            chain_rows,
            singleton_reference,
            symbol_field="first_symbol",
        )

        self.base._write_parquet(self.reference_path, analysis.reference_rows, "symbol")
        self.base._write_parquet(
            self.base.segment_path,
            annotated_segments,
            "identity_chain_id, chain_position, symbol",
        )
        self.base._write_parquet(
            self.base.chain_path,
            annotated_chains,
            "first_symbol, identity_chain_id",
        )

        parent_chains = int(parent.get("identity_chains", -1))
        parent_segments = int(parent.get("identity_segments", -1))
        resulting_chains = len(annotated_chains)
        resulting_segments = len(annotated_segments)

        report = AlpacaBackfillIdentityAssetRiskReport(
            contract_version=ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
            parent_segment_policy_contract_version=ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            asset_state_role=ASSET_ID_REFERENCE_POLICY,
            historical_identity_effect=ASSET_ID_HISTORICAL_EFFECT,
            raw_asset_payloads=retained_payloads,
            raw_asset_rows=analysis.raw_asset_rows,
            raw_exact_symbols=analysis.raw_exact_symbols,
            distinct_symbol_asset_id_pairs=analysis.distinct_symbol_asset_id_pairs,
            symbols_with_multiple_asset_ids=analysis.symbols_with_multiple_asset_ids,
            observed_symbols_with_multiple_asset_ids=analysis.observed_symbols_with_multiple_asset_ids,
            reuse_touching_eligible_edge=analysis.reuse_touching_eligible_edge,
            reuse_touching_quarantined_edge=analysis.reuse_touching_quarantined_edge,
            reuse_in_multi_symbol_chain=analysis.reuse_in_multi_symbol_chain,
            reference_rows=len(analysis.reference_rows),
            segment_reference_annotations=segment_annotations,
            chain_reference_annotations=chain_annotations,
            parent_identity_chains=parent_chains,
            parent_identity_segments=parent_segments,
            resulting_identity_chains=resulting_chains,
            resulting_identity_segments=resulting_segments,
            historical_chain_structure_unchanged=(
                resulting_chains == parent_chains and resulting_segments == parent_segments
            ),
            reference_policy_is_non_segmenting=(
                analysis.reuse_touching_eligible_edge == 0
                and analysis.reuse_touching_quarantined_edge == 0
                and analysis.reuse_in_multi_symbol_chain == 0
                and segment_annotations == len(analysis.reference_rows)
                and chain_annotations == len(analysis.reference_rows)
            ),
            reference_artifact_path=str(self.reference_path),
            chain_path=str(self.base.chain_path),
            segment_path=str(self.base.segment_path),
            report_path=str(self.report_path),
        )

        if not report.historical_chain_structure_unchanged or not report.reference_policy_is_non_segmenting:
            raise RuntimeError("Gate 4-D asset-ID reference risk invariants failed")

        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
