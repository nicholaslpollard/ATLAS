from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity_policy import (
    ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
    MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS,
)


ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION = (
    "historical-backfill-identity-segments-v1-safe-rename-linear-chains"
)


@dataclass(frozen=True, slots=True)
class IdentitySegmentBuildResult:
    edge_rows: list[dict[str, object]]
    chain_rows: list[dict[str, object]]
    segment_rows: list[dict[str, object]]
    safe_candidate_rows: int
    duplicate_safe_candidate_rows: int


@dataclass(frozen=True, slots=True)
class AlpacaBackfillIdentitySegmentReport:
    contract_version: str
    identity_policy_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    observed_symbols: int
    safe_candidate_rows: int
    unique_safe_edges: int
    duplicate_safe_candidate_rows: int
    identity_chains: int
    identity_segments: int
    singleton_chains: int
    multi_symbol_chains: int
    max_chain_length: int
    expected_chain_count: int
    edge_component_accounting: bool
    chain_coverage_exact: bool
    safe_edges_consumed_exact: bool
    safe_edge_path: str
    chain_path: str
    segment_path: str
    report_path: str


def _text(value: object) -> str | None:
    """Return exact text without applying dataframe-style NA token semantics.

    Gate 4 identity work operates on provider-native literals. Strings such as
    ``NAN`` are valid ticker text and must never be interpreted as missing just
    because a dataframe library commonly uses similar display tokens for nulls.
    Native DuckDB rows represent SQL NULL as ``None``, so only actual ``None``
    and empty/whitespace text are treated as missing here.
    """

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_date(value: object) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _observed_map(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    observed: dict[str, dict[str, object]] = {}
    for row in rows:
        if not bool(row.get("observed")):
            continue
        symbol = _text(row.get("symbol"))
        first_date = _as_date(row.get("first_timestamp"))
        last_date = _as_date(row.get("last_timestamp"))
        if symbol is None or first_date is None or last_date is None:
            raise RuntimeError("observed Gate 3 symbol row lacks exact symbol/time boundaries")
        if first_date > last_date:
            raise RuntimeError(f"observed Gate 3 symbol has inverted bounds: {symbol}")
        if symbol in observed:
            raise RuntimeError(f"duplicate observed Gate 3 symbol: {symbol}")
        observed[symbol] = {
            "symbol": symbol,
            "first_date": first_date,
            "last_date": last_date,
        }
    return observed


def _safe_edge_rows(
    observed: dict[str, dict[str, object]],
    rename_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int, int]:
    pair_rows: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    all_pair_statuses: dict[tuple[str, str], set[str]] = defaultdict(set)
    safe_candidate_rows = 0

    for row in rename_rows:
        source = _text(row.get("old_symbol"))
        target = _text(row.get("new_symbol"))
        status = _text(row.get("status"))
        if source is None or target is None:
            continue
        pair = (source, target)
        if status is not None:
            all_pair_statuses[pair].add(status)
        if status == "SAFE_STITCH_CANDIDATE" and bool(row.get("safe_to_stitch")):
            safe_candidate_rows += 1
            pair_rows[pair].append(row)

    edges: list[dict[str, object]] = []
    duplicate_safe_rows = 0

    for pair in sorted(pair_rows):
        source, target = pair
        rows = pair_rows[pair]
        duplicate_safe_rows += max(0, len(rows) - 1)

        statuses = all_pair_statuses[pair]
        if statuses != {"SAFE_STITCH_CANDIDATE"}:
            raise RuntimeError(
                f"Gate 4-C refuses mixed-status rename pair {source!r}->{target!r}: "
                f"{sorted(statuses)}"
            )
        if source == target:
            raise RuntimeError(f"Gate 4-C refuses self rename edge: {source!r}")
        if source not in observed or target not in observed:
            raise RuntimeError(
                f"Gate 4-C safe rename endpoint is not Gate 3 observed: {source!r}->{target!r}"
            )

        cusips: set[str] = set()
        event_keys: list[str] = []
        provider_event_ids: list[str] = []

        for row in rows:
            old_cusip = _text(row.get("old_cusip"))
            new_cusip = _text(row.get("new_cusip"))
            if old_cusip is None or new_cusip is None or old_cusip != new_cusip:
                raise RuntimeError(
                    f"Gate 4-C safe rename lacks one matching CUSIP: {source!r}->{target!r}"
                )
            cusips.add(old_cusip)
            event_key = _text(row.get("event_key"))
            provider_event_id = _text(row.get("provider_event_id"))
            if event_key is not None:
                event_keys.append(event_key)
            if provider_event_id is not None:
                provider_event_ids.append(provider_event_id)

        if len(cusips) != 1:
            raise RuntimeError(
                f"Gate 4-C safe rename pair has conflicting CUSIPs: {source!r}->{target!r} "
                f"{sorted(cusips)}"
            )

        old_last = observed[source]["last_date"]
        new_first = observed[target]["first_date"]
        assert isinstance(old_last, date)
        assert isinstance(new_first, date)
        if old_last >= new_first:
            raise RuntimeError(
                f"Gate 4-C safe rename actually overlaps: {source!r}->{target!r}"
            )
        gap = (new_first - old_last).days
        if gap < 1 or gap > MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS:
            raise RuntimeError(
                f"Gate 4-C safe rename violates handoff policy: {source!r}->{target!r} gap={gap}"
            )

        edge_payload = {
            "old_symbol": source,
            "new_symbol": target,
            "cusip": next(iter(cusips)),
            "old_last_date": old_last.isoformat(),
            "new_first_date": new_first.isoformat(),
            "handoff_gap_calendar_days": gap,
            "evidence_event_count": len(rows),
            "provider_event_ids_json": json.dumps(sorted(set(provider_event_ids))),
            "event_keys_json": json.dumps(sorted(set(event_keys))),
        }
        edge_id_payload = json.dumps(
            {
                "contract": ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
                "old_symbol": source,
                "new_symbol": target,
                "cusip": edge_payload["cusip"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        edge_payload["safe_edge_id"] = hashlib.sha256(edge_id_payload).hexdigest()
        edges.append(edge_payload)

    return edges, safe_candidate_rows, duplicate_safe_rows


def build_identity_segments(
    observed_rows: list[dict[str, object]],
    rename_rows: list[dict[str, object]],
) -> IdentitySegmentBuildResult:
    """Build exact-symbol identity chains using only Gate 4-B safe rename edges."""

    observed = _observed_map(observed_rows)
    edges, safe_candidate_rows, duplicate_safe_rows = _safe_edge_rows(observed, rename_rows)

    successor: dict[str, str] = {}
    predecessor: dict[str, str] = {}
    edge_by_pair: dict[tuple[str, str], dict[str, object]] = {}

    for edge in edges:
        source = str(edge["old_symbol"])
        target = str(edge["new_symbol"])
        if source in successor and successor[source] != target:
            raise RuntimeError(f"Gate 4-C safe-edge branching at source {source!r}")
        if target in predecessor and predecessor[target] != source:
            raise RuntimeError(f"Gate 4-C safe-edge branching at target {target!r}")
        successor[source] = target
        predecessor[target] = source
        edge_by_pair[(source, target)] = edge

    for symbol in sorted(set(successor) | set(predecessor)):
        seen: set[str] = set()
        current = symbol
        while current in successor:
            if current in seen:
                raise RuntimeError(f"Gate 4-C safe rename graph contains a cycle at {current!r}")
            seen.add(current)
            current = successor[current]

    connected_symbols = set(successor) | set(predecessor)
    roots = sorted(symbol for symbol in connected_symbols if symbol not in predecessor)

    chains: list[list[str]] = []
    covered: set[str] = set()

    for root in roots:
        chain: list[str] = []
        current = root
        while True:
            if current in covered:
                raise RuntimeError(f"Gate 4-C symbol appears in multiple safe chains: {current!r}")
            chain.append(current)
            covered.add(current)
            if current not in successor:
                break
            current = successor[current]
        chains.append(chain)

    if covered != connected_symbols:
        missing = sorted(connected_symbols - covered)
        raise RuntimeError(f"Gate 4-C safe graph has unrooted/cyclic symbols: {missing[:10]}")

    for symbol in sorted(set(observed) - connected_symbols):
        chains.append([symbol])

    chains.sort(key=lambda members: tuple(members))

    chain_rows: list[dict[str, object]] = []
    segment_rows: list[dict[str, object]] = []

    for members in chains:
        edge_rows = [
            edge_by_pair[(members[index], members[index + 1])]
            for index in range(len(members) - 1)
        ]
        chain_cusips = {str(edge["cusip"]) for edge in edge_rows}
        if len(chain_cusips) > 1:
            raise RuntimeError(
                f"Gate 4-C multi-edge chain changes CUSIP across safe renames: {members}"
            )
        chain_cusip = next(iter(chain_cusips)) if chain_cusips else None

        chain_id_payload = json.dumps(
            {
                "contract": ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
                "symbols": members,
                "cusip": chain_cusip,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        chain_id = hashlib.sha256(chain_id_payload).hexdigest()

        first_date = min(observed[symbol]["first_date"] for symbol in members)
        last_date = max(observed[symbol]["last_date"] for symbol in members)
        assert isinstance(first_date, date)
        assert isinstance(last_date, date)

        chain_rows.append(
            {
                "identity_chain_id": chain_id,
                "chain_length": len(members),
                "safe_edge_count": len(edge_rows),
                "first_symbol": members[0],
                "last_symbol": members[-1],
                "cusip": chain_cusip,
                "chain_first_date": first_date.isoformat(),
                "chain_last_date": last_date.isoformat(),
                "member_symbols_json": json.dumps(members),
                "continuity_basis": (
                    "SAFE_NAME_CHANGE_CHAIN"
                    if len(members) > 1
                    else "OBSERVED_LITERAL_SINGLETON"
                ),
            }
        )

        for position, symbol in enumerate(members):
            incoming = (
                edge_by_pair[(members[position - 1], symbol)]
                if position > 0
                else None
            )
            outgoing = (
                edge_by_pair[(symbol, members[position + 1])]
                if position + 1 < len(members)
                else None
            )
            segment_id_payload = json.dumps(
                {
                    "chain_id": chain_id,
                    "position": position,
                    "symbol": symbol,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            segment_rows.append(
                {
                    "identity_chain_id": chain_id,
                    "segment_id": hashlib.sha256(segment_id_payload).hexdigest(),
                    "chain_position": position,
                    "chain_length": len(members),
                    "symbol": symbol,
                    "cusip": chain_cusip,
                    "first_date": observed[symbol]["first_date"].isoformat(),
                    "last_date": observed[symbol]["last_date"].isoformat(),
                    "predecessor_symbol": members[position - 1] if position > 0 else None,
                    "successor_symbol": (
                        members[position + 1] if position + 1 < len(members) else None
                    ),
                    "incoming_handoff_gap_calendar_days": (
                        int(incoming["handoff_gap_calendar_days"]) if incoming else None
                    ),
                    "outgoing_handoff_gap_calendar_days": (
                        int(outgoing["handoff_gap_calendar_days"]) if outgoing else None
                    ),
                    "incoming_provider_event_ids_json": (
                        incoming["provider_event_ids_json"] if incoming else None
                    ),
                    "outgoing_provider_event_ids_json": (
                        outgoing["provider_event_ids_json"] if outgoing else None
                    ),
                    "continuity_basis": (
                        "SAFE_NAME_CHANGE_CHAIN"
                        if len(members) > 1
                        else "OBSERVED_LITERAL_SINGLETON"
                    ),
                }
            )

    if len(segment_rows) != len(observed):
        raise RuntimeError(
            f"Gate 4-C segment coverage mismatch: segments={len(segment_rows)} "
            f"observed={len(observed)}"
        )
    if len(chain_rows) != len(observed) - len(edges):
        raise RuntimeError(
            f"Gate 4-C edge/component accounting mismatch: chains={len(chain_rows)} "
            f"observed={len(observed)} unique_edges={len(edges)}"
        )

    return IdentitySegmentBuildResult(
        edge_rows=edges,
        chain_rows=chain_rows,
        segment_rows=segment_rows,
        safe_candidate_rows=safe_candidate_rows,
        duplicate_safe_candidate_rows=duplicate_safe_rows,
    )


class AlpacaBackfillIdentitySegmentBuilder:
    """Materialize Gate 4-C identity chains without touching canonical history."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived_root = settings.resolved_path(settings.data.paths.derived)
        root = derived_root / "historical_backfill" / "alpaca"
        self.acquisition_report_path = root / "acquisition" / "acquisition_report.json"
        self.observed_summary_path = root / "acquisition" / "observed_symbols.parquet"
        self.identity_report_path = root / "identity" / "identity_report.json"
        self.rename_candidate_path = root / "identity" / "rename_continuity_candidates.parquet"
        self.identity_root = root / "identity"
        self.safe_edge_path = self.identity_root / "safe_rename_edges.parquet"
        self.chain_path = self.identity_root / "identity_chains.parquet"
        self.segment_path = self.identity_root / "identity_segments.parquet"
        self.report_path = self.identity_root / "identity_segment_report.json"

    def _load_parent_reports(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.acquisition_report_path.is_file():
            raise RuntimeError("Gate 4-C requires the accepted Gate 3 acquisition report")
        if not self.identity_report_path.is_file():
            raise RuntimeError("Gate 4-C requires the Gate 4-B identity report")

        acquisition = json.loads(self.acquisition_report_path.read_text(encoding="utf-8"))
        identity = json.loads(self.identity_report_path.read_text(encoding="utf-8"))

        if acquisition.get("complete") is not True or int(acquisition.get("missing_units", -1)) != 0:
            raise RuntimeError("Gate 4-C requires complete Gate 3 acquisition")
        if acquisition.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 4-C Gate 3 report does not preserve canonical safety")
        if identity.get("contract_version") != ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION:
            raise RuntimeError("Gate 4-C requires the accepted Gate 4-B identity policy contract")
        if identity.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 4-C identity report does not preserve canonical safety")
        return acquisition, identity

    @staticmethod
    def _read_rows(
        path: Path,
        order_by: str,
        *,
        where: str | None = None,
    ) -> list[dict[str, object]]:
        """Read Parquet rows as native DuckDB values, never via pandas coercion."""

        if not path.is_file():
            raise RuntimeError(f"Gate 4-C required artifact is missing: {path}")
        query = "SELECT * FROM read_parquet(?)"
        if where:
            query += f" WHERE {where}"
        query += f" ORDER BY {order_by}"

        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(query, [str(path)])
            columns = [column[0] for column in cursor.description]
            values = cursor.fetchall()
        finally:
            con.close()
        return [dict(zip(columns, row)) for row in values]

    @staticmethod
    def _write_parquet(path: Path, rows: list[dict[str, object]], order_by: str) -> None:
        frame = pd.DataFrame(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(path)
        con = duckdb.connect(":memory:")
        try:
            con.register("artifact_df", frame)
            con.execute(
                f"COPY (SELECT * FROM artifact_df ORDER BY {order_by}) TO ? "
                "(FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, path)

    def run(self) -> AlpacaBackfillIdentitySegmentReport:
        _acquisition, identity = self._load_parent_reports()
        observed_rows = self._read_rows(
            self.observed_summary_path,
            "symbol",
            where="observed = TRUE",
        )
        rename_rows = self._read_rows(
            self.rename_candidate_path,
            "event_date NULLS LAST, old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
        )

        result = build_identity_segments(observed_rows, rename_rows)
        observed_count = len(observed_rows)
        unique_edges = len(result.edge_rows)
        expected_chains = observed_count - unique_edges
        chain_count = len(result.chain_rows)
        segment_count = len(result.segment_rows)
        singleton_chains = sum(1 for row in result.chain_rows if int(row["chain_length"]) == 1)
        multi_symbol_chains = chain_count - singleton_chains
        max_chain_length = max((int(row["chain_length"]) for row in result.chain_rows), default=0)

        if result.safe_candidate_rows != int(identity.get("safe_stitch_candidates", -1)):
            raise RuntimeError(
                "Gate 4-C safe candidate row count does not match Gate 4-B report: "
                f"rows={result.safe_candidate_rows} "
                f"report={identity.get('safe_stitch_candidates')}"
            )

        self._write_parquet(
            self.safe_edge_path,
            result.edge_rows,
            "old_symbol, new_symbol, safe_edge_id",
        )
        self._write_parquet(
            self.chain_path,
            result.chain_rows,
            "first_symbol, identity_chain_id",
        )
        self._write_parquet(
            self.segment_path,
            result.segment_rows,
            "identity_chain_id, chain_position, symbol",
        )

        report = AlpacaBackfillIdentitySegmentReport(
            contract_version=ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
            identity_policy_contract_version=ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            observed_symbols=observed_count,
            safe_candidate_rows=result.safe_candidate_rows,
            unique_safe_edges=unique_edges,
            duplicate_safe_candidate_rows=result.duplicate_safe_candidate_rows,
            identity_chains=chain_count,
            identity_segments=segment_count,
            singleton_chains=singleton_chains,
            multi_symbol_chains=multi_symbol_chains,
            max_chain_length=max_chain_length,
            expected_chain_count=expected_chains,
            edge_component_accounting=chain_count == expected_chains,
            chain_coverage_exact=segment_count == observed_count,
            safe_edges_consumed_exact=unique_edges == sum(
                int(row["safe_edge_count"]) for row in result.chain_rows
            ),
            safe_edge_path=str(self.safe_edge_path),
            chain_path=str(self.chain_path),
            segment_path=str(self.segment_path),
            report_path=str(self.report_path),
        )

        if not (
            report.edge_component_accounting
            and report.chain_coverage_exact
            and report.safe_edges_consumed_exact
        ):
            raise RuntimeError("Gate 4-C identity-chain validation invariant failed")

        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
