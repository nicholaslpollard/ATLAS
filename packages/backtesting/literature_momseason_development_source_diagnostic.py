from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_development import _rows_fingerprint
from .literature_momseason_development_target_transport import (
    MomSeasonDevelopmentResearchTargetTransportSafe,
)
from .literature_momseason_source import canonical_json, read_gzip_jsonl


LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_CONTRACT = (
    "lit01-development-source-incomplete-diagnostic-v1-cached-target-manifests-no-provider-reads"
)
LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS = (
    "LIT01_DEVELOPMENT_SOURCE_INCOMPLETE_DIAGNOSTIC_READY"
)
LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT = "development_source_incomplete_diagnostic.json"


def _holding_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row["target_month"]),
        str(row["hypothesis_id"]),
        str(row["side"]),
        str(row["instrument_id"]),
    )


def diagnose_cached_source_rows(
    *,
    plan_rows: list[dict[str, object]],
    holdings: list[dict[str, object]],
    source_results: Mapping[tuple[date, str], Mapping[str, object]],
) -> dict[str, object]:
    """Explain source-incomplete frozen rows without changing scientific inputs.

    ``source_results`` is keyed only by provider transport identity
    ``(endpoint_session, historical_ticker)``.  The frozen plan remains keyed by
    ``(endpoint_session, instrument_id)`` and can therefore contain multiple rows that
    legitimately share one provider observation.
    """

    unavailable_by_plan_key: dict[tuple[date, str], dict[str, object]] = {}
    unavailable_source_keys: dict[tuple[date, str], dict[str, object]] = {}
    status_counts: Counter[str] = Counter()

    for plan in plan_rows:
        endpoint = date.fromisoformat(str(plan["endpoint_session"]))
        instrument_id = str(plan["instrument_id"])
        ticker = str(plan["historical_ticker"])
        source = source_results.get((endpoint, ticker))
        status = (
            "TARGET_UNIT_NOT_MATERIALIZED"
            if source is None
            else str(source.get("availability_status") or "UNKNOWN")
        )
        if status == "AVAILABLE":
            continue
        status_counts[status] += 1
        plan_key = (endpoint, instrument_id)
        unavailable_by_plan_key[plan_key] = {
            "endpoint_session": endpoint.isoformat(),
            "instrument_id": instrument_id,
            "historical_ticker": ticker,
            "availability_status": status,
        }
        group = unavailable_source_keys.setdefault(
            (endpoint, ticker),
            {
                "endpoint_session": endpoint.isoformat(),
                "historical_ticker": ticker,
                "availability_status": status,
                "instrument_ids": [],
                "prior_holding_hits": 0,
                "target_holding_hits": 0,
                "blocked_holding_keys": set(),
                "hypotheses": set(),
                "target_months": set(),
            },
        )
        if group["availability_status"] != status:
            raise RuntimeError(
                "conflicting cached source status for one LIT-01 endpoint/ticker: "
                f"{endpoint} {ticker}"
            )
        group["instrument_ids"].append(instrument_id)

    blocked_holdings: dict[tuple[str, str, str, str], set[tuple[date, str]]] = defaultdict(set)
    for holding in holdings:
        instrument_id = str(holding["instrument_id"])
        holding_key = _holding_key(holding)
        hypothesis_id = str(holding["hypothesis_id"])
        target_month = str(holding["target_month"])
        endpoint_roles = (
            ("PRIOR", date.fromisoformat(str(holding["prior_endpoint_session"]))),
            ("TARGET", date.fromisoformat(str(holding["target_endpoint_session"]))),
        )
        for role, endpoint in endpoint_roles:
            missing = unavailable_by_plan_key.get((endpoint, instrument_id))
            if missing is None:
                continue
            source_key = (endpoint, str(missing["historical_ticker"]))
            group = unavailable_source_keys[source_key]
            if role == "PRIOR":
                group["prior_holding_hits"] += 1
            else:
                group["target_holding_hits"] += 1
            group["blocked_holding_keys"].add(holding_key)
            group["hypotheses"].add(hypothesis_id)
            group["target_months"].add(target_month)
            blocked_holdings[holding_key].add((endpoint, instrument_id))

    details: list[dict[str, object]] = []
    for source_key in sorted(unavailable_source_keys):
        group = unavailable_source_keys[source_key]
        details.append(
            {
                "endpoint_session": group["endpoint_session"],
                "historical_ticker": group["historical_ticker"],
                "availability_status": group["availability_status"],
                "instrument_ids": sorted(set(group["instrument_ids"])),
                "instrument_rows": len(set(group["instrument_ids"])),
                "prior_holding_hits": int(group["prior_holding_hits"]),
                "target_holding_hits": int(group["target_holding_hits"]),
                "blocked_holdings": len(group["blocked_holding_keys"]),
                "hypotheses": sorted(group["hypotheses"]),
                "target_months": sorted(group["target_months"]),
            }
        )

    blocked_by_hypothesis: Counter[str] = Counter(key[1] for key in blocked_holdings)
    blocked_by_month: Counter[str] = Counter(key[0] for key in blocked_holdings)
    return {
        "unavailable_plan_rows": len(unavailable_by_plan_key),
        "unavailable_source_keys": len(unavailable_source_keys),
        "unavailable_status_counts": dict(sorted(status_counts.items())),
        "blocked_holdings": len(blocked_holdings),
        "blocked_holdings_by_hypothesis": dict(sorted(blocked_by_hypothesis.items())),
        "blocked_holdings_by_target_month": dict(sorted(blocked_by_month.items())),
        "details": details,
    }


class MomSeasonDevelopmentSourceIncompleteDiagnostic:
    """Read only frozen plans/manifests and explain why development is incomplete."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.runner = MomSeasonDevelopmentResearchTargetTransportSafe(settings)

    def report_path(self):
        return self.runner.root / LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT

    def _cached_source_results(self) -> tuple[dict[tuple[date, str], dict[str, object]], int]:
        results: dict[tuple[date, str], dict[str, object]] = {}
        missing_units = 0
        for unit in self.runner.build_units():
            manifest = self.runner._load_completed_manifest(unit)
            if manifest is None:
                missing_units += 1
                continue
            for row in manifest.get("symbol_results") or []:
                if not isinstance(row, Mapping):
                    continue
                key = (unit.endpoint_session, str(row["symbol"]))
                value = dict(row)
                existing = results.get(key)
                if existing is not None and existing != value:
                    raise RuntimeError(
                        "conflicting cached LIT-01 target source result for "
                        f"{unit.endpoint_session} {row['symbol']}"
                    )
                results[key] = value
        return results, missing_units

    def run(self) -> dict[str, object]:
        self.runner._require_freeze()
        plan_rows, plan_report = self.runner._load_target_plan()
        holdings = read_gzip_jsonl(self.runner.holdings_path())
        if _rows_fingerprint(holdings) != plan_report.get("holdings_fingerprint"):
            raise RuntimeError("LIT-01 diagnostic holdings fingerprint mismatch")

        source_results, missing_units = self._cached_source_results()
        diagnostic = diagnose_cached_source_rows(
            plan_rows=plan_rows,
            holdings=holdings,
            source_results=source_results,
        )
        report = {
            "status": LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
            "contract_version": LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_CONTRACT,
            "freeze_fingerprint": str(plan_report["freeze_fingerprint"]),
            "holdings_fingerprint": str(plan_report["holdings_fingerprint"]),
            "target_plan_fingerprint": str(plan_report["target_plan_fingerprint"]),
            "holdings_rows": len(holdings),
            "target_plan_rows": len(plan_rows),
            "cached_transport_source_keys": len(source_results),
            "missing_target_units": missing_units,
            **diagnostic,
            "scientific_interpretation": (
                "SOURCE_INTEGRITY_ONLY_NOT_ALPHA_REJECTION; no missing return may be zero-filled, "
                "last-price-filled, silently deleted, or used to retune the frozen hypotheses"
            ),
            "provider_reads_performed": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_path())
        return report
