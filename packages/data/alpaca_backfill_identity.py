from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_acquisition import ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_CONTRACT_VERSION


ALPACA_BACKFILL_IDENTITY_CONTRACT_VERSION = (
    "historical-backfill-identity-v1-retained-corporate-action-evidence"
)
CORPORATE_ACTION_PARTITION_PREFIX = "corporate_actions_2016_2021_page_"

KNOWN_EVENT_TYPES = {
    "cash_dividends",
    "reverse_splits",
    "stock_mergers",
    "name_changes",
    "forward_splits",
    "cash_mergers",
    "stock_dividends",
    "unit_splits",
    "stock_and_cash_mergers",
    "spin_offs",
    "rights_distributions",
}
MERGER_EVENT_TYPES = {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"}
DISTRIBUTION_EVENT_TYPES = {"cash_dividends", "stock_dividends"}
SHARE_STRUCTURE_EVENT_TYPES = {"forward_splits", "reverse_splits"}
DERIVED_SECURITY_EVENT_TYPES = {"spin_offs", "rights_distributions"}


@dataclass(frozen=True, slots=True)
class ObservedBounds:
    first_date: date | None
    last_date: date | None
    observed: bool


@dataclass(frozen=True, slots=True)
class AlpacaBackfillIdentityReport:
    contract_version: str
    parent_contract_version: str
    inventory_contract_version: str
    acquisition_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    retained_corporate_action_pages: int
    expected_corporate_action_pages: int
    raw_payload_hash_failures: int
    corporate_action_events: int
    event_type_counts: dict[str, int]
    unknown_event_types: list[str]
    duplicate_provider_event_ids: int
    identity_relationship_rows: int
    structural_event_rows: int
    rename_continuity_candidates: int
    safe_stitch_candidates: int
    continuity_evidence_only: int
    rename_review_required: int
    gate3_casefold_sensitive_candidates: int
    event_ledger_path: str
    relationship_path: str
    rename_candidate_path: str
    report_path: str


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_symbol(value: object) -> str | None:
    symbol = _clean_text(value)
    if symbol is None or "," in symbol or any(ch.isspace() for ch in symbol):
        return None
    return symbol


def _clean_cusip(value: object) -> str | None:
    return _clean_text(value)


def _event_date(record: dict[str, Any]) -> str | None:
    for key in ("effective_date", "ex_date", "process_date"):
        value = _clean_text(record.get(key))
        if value is not None:
            return value
    return None


def _date_from_text(value: object) -> date | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text)
    except ValueError:
        return None


def _event_semantics(event_type: str) -> str:
    if event_type == "name_changes":
        return "RENAME_CONTINUITY_CANDIDATE"
    if event_type in MERGER_EVENT_TYPES:
        return "TERMINATION_CONVERSION"
    if event_type in DERIVED_SECURITY_EVENT_TYPES:
        return "DERIVED_SECURITY"
    if event_type == "unit_splits":
        return "UNIT_DECOMPOSITION"
    if event_type in SHARE_STRUCTURE_EVENT_TYPES:
        return "SHARE_STRUCTURE"
    if event_type in DISTRIBUTION_EVENT_TYPES:
        return "DISTRIBUTION"
    return "UNKNOWN_EVENT_TYPE"


def _normalize_event(
    event_type: str,
    record: dict[str, Any],
    *,
    partition: str,
    raw_sha256: str,
    event_index: int,
) -> dict[str, object]:
    source_symbol: str | None = None
    source_cusip: str | None = None
    target_symbol: str | None = None
    target_cusip: str | None = None
    alternate_symbol: str | None = None
    alternate_cusip: str | None = None

    if event_type == "name_changes":
        source_symbol = _clean_symbol(record.get("old_symbol"))
        source_cusip = _clean_cusip(record.get("old_cusip"))
        target_symbol = _clean_symbol(record.get("new_symbol"))
        target_cusip = _clean_cusip(record.get("new_cusip"))
    elif event_type in MERGER_EVENT_TYPES:
        source_symbol = _clean_symbol(record.get("acquiree_symbol"))
        source_cusip = _clean_cusip(record.get("acquiree_cusip"))
        target_symbol = _clean_symbol(record.get("acquirer_symbol"))
        target_cusip = _clean_cusip(record.get("acquirer_cusip"))
    elif event_type in DERIVED_SECURITY_EVENT_TYPES:
        source_symbol = _clean_symbol(record.get("source_symbol"))
        source_cusip = _clean_cusip(record.get("source_cusip"))
        target_symbol = _clean_symbol(record.get("new_symbol"))
        target_cusip = _clean_cusip(record.get("new_cusip"))
    elif event_type == "unit_splits":
        source_symbol = _clean_symbol(record.get("old_symbol"))
        source_cusip = _clean_cusip(record.get("old_cusip"))
        target_symbol = _clean_symbol(record.get("new_symbol"))
        target_cusip = _clean_cusip(record.get("new_cusip"))
        alternate_symbol = _clean_symbol(record.get("alternate_symbol"))
        alternate_cusip = _clean_cusip(record.get("alternate_cusip"))
    elif event_type == "reverse_splits":
        source_symbol = _clean_symbol(record.get("symbol"))
        source_cusip = _clean_cusip(record.get("old_cusip"))
        target_symbol = source_symbol
        target_cusip = _clean_cusip(record.get("new_cusip"))
    else:
        source_symbol = _clean_symbol(record.get("symbol"))
        source_cusip = _clean_cusip(record.get("cusip"))

    provider_event_id = _clean_text(record.get("id"))
    event_key_payload = json.dumps(
        {
            "partition": partition,
            "event_type": event_type,
            "event_index": event_index,
            "provider_event_id": provider_event_id,
            "raw_sha256": raw_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return {
        "event_key": hashlib.sha256(event_key_payload).hexdigest(),
        "provider_event_id": provider_event_id,
        "event_type": event_type,
        "identity_semantics": _event_semantics(event_type),
        "event_date": _event_date(record),
        "process_date": _clean_text(record.get("process_date")),
        "ex_date": _clean_text(record.get("ex_date")),
        "effective_date": _clean_text(record.get("effective_date")),
        "source_symbol": source_symbol,
        "source_cusip": source_cusip,
        "target_symbol": target_symbol,
        "target_cusip": target_cusip,
        "alternate_symbol": alternate_symbol,
        "alternate_cusip": alternate_cusip,
        "raw_partition": partition,
        "raw_sha256": raw_sha256,
        "raw_event_index": event_index,
        "provider_record_json": json.dumps(record, sort_keys=True, separators=(",", ":")),
    }


def _relationship_rows(event: dict[str, object]) -> list[dict[str, object]]:
    event_type = str(event["event_type"])
    source_symbol = event.get("source_symbol")
    target_symbol = event.get("target_symbol")
    rows: list[dict[str, object]] = []

    def append_relation(
        relation_type: str,
        *,
        target: object,
        target_cusip: object,
        continuity_candidate: bool,
        continuity_forbidden: bool,
    ) -> None:
        relation_payload = json.dumps(
            {
                "event_key": event["event_key"],
                "relation_type": relation_type,
                "source_symbol": source_symbol,
                "target_symbol": target,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        rows.append(
            {
                "relationship_id": hashlib.sha256(relation_payload).hexdigest(),
                "event_key": event["event_key"],
                "provider_event_id": event.get("provider_event_id"),
                "event_type": event_type,
                "event_date": event.get("event_date"),
                "relation_type": relation_type,
                "source_symbol": source_symbol,
                "source_cusip": event.get("source_cusip"),
                "target_symbol": target,
                "target_cusip": target_cusip,
                "continuity_candidate": continuity_candidate,
                "continuity_forbidden": continuity_forbidden,
            }
        )

    if event_type == "name_changes":
        append_relation(
            "RENAME",
            target=target_symbol,
            target_cusip=event.get("target_cusip"),
            continuity_candidate=True,
            continuity_forbidden=False,
        )
    elif event_type in MERGER_EVENT_TYPES:
        append_relation(
            "TERMINATION_CONVERSION",
            target=target_symbol,
            target_cusip=event.get("target_cusip"),
            continuity_candidate=False,
            continuity_forbidden=True,
        )
    elif event_type == "spin_offs":
        append_relation(
            "SPINOFF_SECURITY",
            target=target_symbol,
            target_cusip=event.get("target_cusip"),
            continuity_candidate=False,
            continuity_forbidden=True,
        )
    elif event_type == "rights_distributions":
        append_relation(
            "RIGHTS_SECURITY",
            target=target_symbol,
            target_cusip=event.get("target_cusip"),
            continuity_candidate=False,
            continuity_forbidden=True,
        )
    elif event_type == "unit_splits":
        append_relation(
            "UNIT_COMMON_COMPONENT",
            target=target_symbol,
            target_cusip=event.get("target_cusip"),
            continuity_candidate=False,
            continuity_forbidden=True,
        )
        append_relation(
            "UNIT_ALTERNATE_COMPONENT",
            target=event.get("alternate_symbol"),
            target_cusip=event.get("alternate_cusip"),
            continuity_candidate=False,
            continuity_forbidden=True,
        )
    return rows


def _cycle_nodes(edges: Iterable[tuple[str, str]]) -> set[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        if source and target and source != target:
            adjacency[source].add(target)

    state: dict[str, int] = {}
    stack: list[str] = []
    stack_index: dict[str, int] = {}
    cycles: set[str] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack_index[node] = len(stack)
        stack.append(node)
        for target in adjacency.get(node, set()):
            if state.get(target, 0) == 0:
                visit(target)
            elif state.get(target) == 1:
                start = stack_index[target]
                cycles.update(stack[start:])
        stack.pop()
        stack_index.pop(node, None)
        state[node] = 2

    for node in sorted(adjacency):
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


def _classify_name_change(
    event: dict[str, object],
    *,
    observed: dict[str, ObservedBounds],
    source_target_count: dict[str, int],
    target_source_count: dict[str, int],
    cycle_nodes: set[str],
    anomaly_casefold_keys: set[str],
) -> dict[str, object]:
    source = _clean_symbol(event.get("source_symbol"))
    target = _clean_symbol(event.get("target_symbol"))
    source_cusip = _clean_cusip(event.get("source_cusip"))
    target_cusip = _clean_cusip(event.get("target_cusip"))
    transition_date = _date_from_text(event.get("event_date"))
    reasons: list[str] = []

    if source is None or target is None:
        reasons.append("MISSING_SYMBOL")
    elif source == target:
        reasons.append("SAME_LITERAL_NO_RENAME")
    elif source.casefold() == target.casefold():
        reasons.append("CASE_ONLY_LITERAL_CHANGE")

    if source_cusip is None or target_cusip is None:
        reasons.append("MISSING_CUSIP")
    elif source_cusip != target_cusip:
        reasons.append("CUSIP_CHANGED")

    if transition_date is None:
        reasons.append("MISSING_EVENT_DATE")

    if source is not None and source_target_count.get(source, 0) > 1:
        reasons.append("SOURCE_BRANCHING")
    if target is not None and target_source_count.get(target, 0) > 1:
        reasons.append("TARGET_BRANCHING")
    if (source is not None and source in cycle_nodes) or (
        target is not None and target in cycle_nodes
    ):
        reasons.append("NAME_CHANGE_CYCLE")

    if source is not None and source.casefold() in anomaly_casefold_keys:
        reasons.append("GATE3_CASEFOLD_ANOMALY")
    if target is not None and target.casefold() in anomaly_casefold_keys:
        reasons.append("GATE3_CASEFOLD_ANOMALY")

    source_bounds = observed.get(source) if source is not None else None
    target_bounds = observed.get(target) if target is not None else None

    if transition_date is not None and source_bounds is not None and source_bounds.last_date is not None:
        if source_bounds.last_date > transition_date:
            reasons.append("OLD_OBSERVED_AFTER_CHANGE")
    if transition_date is not None and target_bounds is not None and target_bounds.first_date is not None:
        if target_bounds.first_date < transition_date:
            reasons.append("NEW_OBSERVED_BEFORE_CHANGE")
    if (
        source_bounds is not None
        and target_bounds is not None
        and source_bounds.last_date is not None
        and target_bounds.first_date is not None
        and source_bounds.last_date >= target_bounds.first_date
    ):
        reasons.append("OBSERVATION_OVERLAP")

    reasons = sorted(set(reasons))
    source_observed = bool(source_bounds and source_bounds.observed)
    target_observed = bool(target_bounds and target_bounds.observed)

    if reasons:
        status = "REVIEW_REQUIRED"
        safe_to_stitch = False
    elif source_observed and target_observed:
        status = "SAFE_STITCH_CANDIDATE"
        safe_to_stitch = True
    else:
        status = "CONTINUITY_EVIDENCE_ONLY"
        safe_to_stitch = False

    return {
        "event_key": event["event_key"],
        "provider_event_id": event.get("provider_event_id"),
        "event_date": event.get("event_date"),
        "old_symbol": source,
        "new_symbol": target,
        "old_cusip": source_cusip,
        "new_cusip": target_cusip,
        "old_observed": source_observed,
        "new_observed": target_observed,
        "old_first_date": (
            source_bounds.first_date.isoformat()
            if source_bounds is not None and source_bounds.first_date is not None
            else None
        ),
        "old_last_date": (
            source_bounds.last_date.isoformat()
            if source_bounds is not None and source_bounds.last_date is not None
            else None
        ),
        "new_first_date": (
            target_bounds.first_date.isoformat()
            if target_bounds is not None and target_bounds.first_date is not None
            else None
        ),
        "new_last_date": (
            target_bounds.last_date.isoformat()
            if target_bounds is not None and target_bounds.last_date is not None
            else None
        ),
        "status": status,
        "safe_to_stitch": safe_to_stitch,
        "review_reasons": ",".join(reasons),
    }


class AlpacaBackfillIdentityBuilder:
    """Materialize Gate 4 identity evidence from retained corporate-action pages only."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.raw_root = provider_root / "alpaca" / "historical_backfill" / "raw" / "v2"
        root = derived_root / "historical_backfill" / "alpaca"
        self.inventory_report_path = root / "inventory" / "inventory_report.json"
        self.acquisition_report_path = root / "acquisition" / "acquisition_report.json"
        self.observed_summary_path = root / "acquisition" / "observed_symbols.parquet"
        self.response_anomaly_path = root / "acquisition" / "response_symbol_anomalies.parquet"
        self.identity_root = root / "identity"
        self.event_ledger_path = self.identity_root / "corporate_action_events.parquet"
        self.relationship_path = self.identity_root / "identity_relationships.parquet"
        self.rename_candidate_path = self.identity_root / "rename_continuity_candidates.parquet"
        self.report_path = self.identity_root / "identity_report.json"

    def _load_parent_reports(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.inventory_report_path.is_file():
            raise RuntimeError("Gate 4 requires the accepted Gate 2 inventory report")
        if not self.acquisition_report_path.is_file():
            raise RuntimeError("Gate 4 requires the accepted Gate 3 acquisition report")
        inventory = json.loads(self.inventory_report_path.read_text(encoding="utf-8"))
        acquisition = json.loads(self.acquisition_report_path.read_text(encoding="utf-8"))
        if inventory.get("contract_version") != ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION:
            raise RuntimeError("Gate 4 inventory contract mismatch")
        if acquisition.get("contract_version") != ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION:
            raise RuntimeError("Gate 4 acquisition contract mismatch")
        if acquisition.get("complete") is not True or int(acquisition.get("missing_units", -1)) != 0:
            raise RuntimeError("Gate 4 requires Gate 3 acquisition to be complete")
        if acquisition.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 3 report does not preserve canonical safety")
        return inventory, acquisition

    def _retained_events(self) -> tuple[list[dict[str, object]], int, int, set[str]]:
        if not self.raw_root.is_dir():
            raise RuntimeError(f"retained Alpaca raw store is missing: {self.raw_root}")

        selected: list[tuple[str, Path, dict[str, Any]]] = []
        for meta_path in self.raw_root.glob("*/*.meta.json"):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("category") != "discovery":
                continue
            partition = str(meta.get("partition") or "")
            if not partition.startswith(CORPORATE_ACTION_PARTITION_PREFIX):
                continue
            selected.append((partition, meta_path, meta))
        selected.sort(key=lambda item: item[0])

        events: list[dict[str, object]] = []
        hash_failures = 0
        unknown_types: set[str] = set()

        for partition, _meta_path, meta in selected:
            payload_path = Path(str(meta.get("payload_path") or ""))
            if not payload_path.is_file():
                raise RuntimeError(f"retained corporate-action payload is missing: {payload_path}")
            raw_bytes = gzip.decompress(payload_path.read_bytes())
            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            expected_sha = str(meta.get("sha256") or "")
            if actual_sha != expected_sha:
                hash_failures += 1
                continue
            payload = json.loads(raw_bytes.decode("utf-8"))
            container = payload.get("corporate_actions") if isinstance(payload, dict) else None
            if not isinstance(container, dict):
                raise RuntimeError(
                    f"retained corporate-action page lacks corporate_actions object: {partition}"
                )
            for event_type in sorted(container):
                values = container[event_type]
                if not isinstance(values, list):
                    raise RuntimeError(
                        f"corporate-action event family is not a list: {event_type} in {partition}"
                    )
                if event_type not in KNOWN_EVENT_TYPES:
                    unknown_types.add(event_type)
                for event_index, record in enumerate(values):
                    if not isinstance(record, dict):
                        raise RuntimeError(
                            f"corporate-action record is not an object: {event_type} in {partition}"
                        )
                    events.append(
                        _normalize_event(
                            event_type,
                            record,
                            partition=partition,
                            raw_sha256=actual_sha,
                            event_index=event_index,
                        )
                    )
        return events, len(selected), hash_failures, unknown_types

    def _load_observed(self) -> dict[str, ObservedBounds]:
        if not self.observed_summary_path.is_file():
            raise RuntimeError("Gate 4 requires the Gate 3 observed-symbol summary")
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT symbol, observed, first_timestamp, last_timestamp "
                "FROM read_parquet(?) ORDER BY symbol",
                [str(self.observed_summary_path)],
            ).fetchall()
        finally:
            con.close()
        result: dict[str, ObservedBounds] = {}
        for symbol, observed, first_timestamp, last_timestamp in rows:
            clean = _clean_symbol(symbol)
            if clean is None:
                continue
            result[clean] = ObservedBounds(
                first_date=_date_from_text(first_timestamp),
                last_date=_date_from_text(last_timestamp),
                observed=bool(observed),
            )
        return result

    def _load_anomaly_casefold_keys(self) -> set[str]:
        if not self.response_anomaly_path.is_file():
            return set()
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT requested_symbol, returned_symbol FROM read_parquet(?)",
                [str(self.response_anomaly_path)],
            ).fetchall()
        finally:
            con.close()
        keys: set[str] = set()
        for requested, returned in rows:
            for value in (requested, returned):
                symbol = _clean_symbol(value)
                if symbol is not None:
                    keys.add(symbol.casefold())
        return keys

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

    def run(self) -> AlpacaBackfillIdentityReport:
        inventory_report, _acquisition_report = self._load_parent_reports()
        events, page_count, hash_failures, unknown_types = self._retained_events()
        if hash_failures:
            raise RuntimeError(
                f"Gate 4 retained corporate-action evidence has {hash_failures} hash failures"
            )

        expected_pages = int(inventory_report.get("corporate_action_pages", 0))
        if page_count != expected_pages:
            raise RuntimeError(
                f"Gate 4 corporate-action page count mismatch: retained={page_count} "
                f"gate2_report={expected_pages}"
            )

        relationships: list[dict[str, object]] = []
        for event in events:
            relationships.extend(_relationship_rows(event))

        name_events = [event for event in events if event["event_type"] == "name_changes"]
        source_targets: dict[str, set[str]] = defaultdict(set)
        target_sources: dict[str, set[str]] = defaultdict(set)
        graph_edges: list[tuple[str, str]] = []
        for event in name_events:
            source = _clean_symbol(event.get("source_symbol"))
            target = _clean_symbol(event.get("target_symbol"))
            if source is None or target is None:
                continue
            source_targets[source].add(target)
            target_sources[target].add(source)
            graph_edges.append((source, target))

        source_target_count = {key: len(value) for key, value in source_targets.items()}
        target_source_count = {key: len(value) for key, value in target_sources.items()}
        cycles = _cycle_nodes(graph_edges)
        observed = self._load_observed()
        anomaly_casefold_keys = self._load_anomaly_casefold_keys()

        rename_candidates = [
            _classify_name_change(
                event,
                observed=observed,
                source_target_count=source_target_count,
                target_source_count=target_source_count,
                cycle_nodes=cycles,
                anomaly_casefold_keys=anomaly_casefold_keys,
            )
            for event in name_events
        ]

        event_counts = Counter(str(event["event_type"]) for event in events)
        provider_ids = [
            str(event["provider_event_id"])
            for event in events
            if event.get("provider_event_id") is not None
        ]
        provider_id_counts = Counter(provider_ids)
        duplicate_provider_event_ids = sum(
            count - 1 for count in provider_id_counts.values() if count > 1
        )
        structural_event_rows = sum(
            1
            for event in events
            if event["identity_semantics"] in {"SHARE_STRUCTURE", "DISTRIBUTION"}
        )
        safe = sum(
            1 for row in rename_candidates if row["status"] == "SAFE_STITCH_CANDIDATE"
        )
        evidence_only = sum(
            1 for row in rename_candidates if row["status"] == "CONTINUITY_EVIDENCE_ONLY"
        )
        review = sum(1 for row in rename_candidates if row["status"] == "REVIEW_REQUIRED")
        gate3_sensitive = sum(
            1
            for row in rename_candidates
            if "GATE3_CASEFOLD_ANOMALY" in str(row["review_reasons"])
        )

        self._write_parquet(
            self.event_ledger_path,
            events,
            "event_type, event_date NULLS LAST, provider_event_id NULLS LAST, event_key",
        )
        self._write_parquet(
            self.relationship_path,
            relationships,
            "event_date NULLS LAST, event_type, source_symbol NULLS LAST, target_symbol NULLS LAST, relationship_id",
        )
        self._write_parquet(
            self.rename_candidate_path,
            rename_candidates,
            "event_date NULLS LAST, old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
        )

        report = AlpacaBackfillIdentityReport(
            contract_version=ALPACA_BACKFILL_IDENTITY_CONTRACT_VERSION,
            parent_contract_version=ALPACA_BACKFILL_CONTRACT_VERSION,
            inventory_contract_version=ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
            acquisition_contract_version=ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            retained_corporate_action_pages=page_count,
            expected_corporate_action_pages=expected_pages,
            raw_payload_hash_failures=hash_failures,
            corporate_action_events=len(events),
            event_type_counts=dict(sorted(event_counts.items())),
            unknown_event_types=sorted(unknown_types),
            duplicate_provider_event_ids=duplicate_provider_event_ids,
            identity_relationship_rows=len(relationships),
            structural_event_rows=structural_event_rows,
            rename_continuity_candidates=len(rename_candidates),
            safe_stitch_candidates=safe,
            continuity_evidence_only=evidence_only,
            rename_review_required=review,
            gate3_casefold_sensitive_candidates=gate3_sensitive,
            event_ledger_path=str(self.event_ledger_path),
            relationship_path=str(self.relationship_path),
            rename_candidate_path=str(self.rename_candidate_path),
            report_path=str(self.report_path),
        )
        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
