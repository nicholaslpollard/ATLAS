from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from packages.backtesting.alpha_gate_xbrl_feasibility import XBRL_REPORT_RELATIVE
from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
    _decision_session,
    _extract_relevant_entries,
    _normalize_cik,
    _resolve_identity,
    accepted_feasibility_evidence_fingerprint,
)
from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_COST_TAG_PRECEDENCE,
    XBRL_DEVELOPMENT_LAST_SIGNAL,
    XBRL_FEATURES,
    XBRL_GROSS_PROFIT_RULE,
    XBRL_HYPOTHESES,
    XBRL_PERFORMANCE_SIGNAL_START,
    XBRL_PREDICTOR_SOURCE_CUTOFF,
    XBRL_PREDICTOR_SOURCE_START,
    XBRL_PROTECTED_LAST_SIGNAL,
    XBRL_PROTECTED_START,
    XBRL_QUARTER_DIRECT_DURATION_DAYS,
    XBRL_REVENUE_TAG_PRECEDENCE,
    XBRL_SCIENTIFIC_FINGERPRINT,
    XBRL_YOY_RULE,
    xbrl_scientific_fingerprint,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient
from packages.providers.sec_xbrl_pit import SECXBRLPITMetadataClient


XBRL_PREDICTOR_CONTRACT = "alpha-gate-xbrl-predictor-v1-accession-pit-quarter-yoy-signals"
XBRL_PREDICTOR_CACHE_RELATIVE = Path("pre_phase33_xbrl_development/v1")
XBRL_PREDICTOR_ROWS_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/xbrl_development_v1/predictor_rows.jsonl"
)
XBRL_PREDICTOR_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/xbrl_development_v1/predictor_report.json"
)
_ALLOWED_FORMS = {"10-Q", "10-K"}
_FLOW_TAGS = (
    "NetIncomeLoss",
    "NetCashProvidedByUsedInOperatingActivities",
    "GrossProfit",
    *XBRL_REVENUE_TAG_PRECEDENCE,
    *XBRL_COST_TAG_PRECEDENCE,
)
_FP_TO_QUARTER = {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}


class XBRLPredictorError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _duration_days(row: Mapping[str, Any]) -> int | None:
    start = _as_date(row.get("start"))
    end = _as_date(row.get("end"))
    if start is None or end is None or end < start:
        return None
    return (end - start).days + 1


def _unique_value(rows: Iterable[Mapping[str, Any]]) -> float | None:
    values = {_as_float(row.get("val")) for row in rows}
    values.discard(None)
    return next(iter(values)) if len(values) == 1 else None


def _rows_for_tag(
    rows: Iterable[dict[str, Any]], *, tag: str, end: date
) -> tuple[dict[str, Any], ...]:
    return tuple(
        row
        for row in rows
        if str(row.get("tag") or "") == tag
        and str(row.get("unit") or "") == "USD"
        and _as_date(row.get("end")) == end
    )


def _instant_value(rows: Iterable[dict[str, Any]], *, tag: str, end: date) -> float | None:
    return _unique_value(
        row for row in _rows_for_tag(rows, tag=tag, end=end) if row.get("start") in (None, "")
    )


def _direct_quarter_value(rows: Iterable[dict[str, Any]], *, tag: str, end: date) -> float | None:
    lower, upper = XBRL_QUARTER_DIRECT_DURATION_DAYS
    return _unique_value(
        row
        for row in _rows_for_tag(rows, tag=tag, end=end)
        if (days := _duration_days(row)) is not None and lower <= days <= upper
    )


def _longest_duration_value(
    rows: Iterable[dict[str, Any]], *, tag: str, end: date, lower: int, upper: int
) -> float | None:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for row in _rows_for_tag(rows, tag=tag, end=end):
        days = _duration_days(row)
        if days is not None and lower <= days <= upper:
            candidates.append((days, row))
    if not candidates:
        return None
    maximum = max(days for days, _ in candidates)
    return _unique_value(row for days, row in candidates if days == maximum)


def _current_period(
    rows: tuple[dict[str, Any], ...], *, filing_date: date, form: str
) -> tuple[date, int, int] | None:
    maximum_age = 180 if form == "10-Q" else 400
    valid_ends = sorted(
        {
            parsed
            for row in rows
            if (parsed := _as_date(row.get("end"))) is not None
            and parsed <= filing_date
            and 0 <= (filing_date - parsed).days <= maximum_age
        }
    )
    if not valid_ends:
        return None
    target_end = valid_ends[-1]
    allowed_fp = {"Q1", "Q2", "Q3"} if form == "10-Q" else {"FY"}
    votes: Counter[tuple[int, str]] = Counter()
    for row in rows:
        if _as_date(row.get("end")) != target_end:
            continue
        fp = str(row.get("fp") or "").strip().upper()
        try:
            fy = int(row.get("fy"))
        except (TypeError, ValueError):
            continue
        if fp in allowed_fp:
            votes[(fy, fp)] += 1
    if not votes:
        return None
    maximum = max(votes.values())
    winners = sorted(key for key, count in votes.items() if count == maximum)
    if len(winners) != 1:
        return None
    fy, fp = winners[0]
    return target_end, fy, _FP_TO_QUARTER[fp]


def _flow_quarter_value(
    rows: tuple[dict[str, Any], ...],
    *,
    tag: str,
    end: date,
    fy: int,
    quarter: int,
    ytd_history: Mapping[tuple[int, int, str], float],
    quarter_history: Mapping[tuple[int, int, str], float],
) -> tuple[float | None, float | None, str | None]:
    direct = _direct_quarter_value(rows, tag=tag, end=end)
    if direct is not None:
        current_ytd: float | None = None
        if quarter == 1:
            current_ytd = direct
        elif quarter == 2:
            current_ytd = _longest_duration_value(rows, tag=tag, end=end, lower=120, upper=230)
        elif quarter == 3:
            current_ytd = _longest_duration_value(rows, tag=tag, end=end, lower=200, upper=320)
        elif quarter == 4:
            current_ytd = _longest_duration_value(rows, tag=tag, end=end, lower=300, upper=380)
        return direct, current_ytd, "DIRECT_QUARTER"

    if quarter == 1:
        current_ytd = _longest_duration_value(rows, tag=tag, end=end, lower=70, upper=110)
        return current_ytd, current_ytd, "Q1_YTD" if current_ytd is not None else None

    if quarter in (2, 3):
        lower, upper = ((120, 230) if quarter == 2 else (200, 320))
        current_ytd = _longest_duration_value(rows, tag=tag, end=end, lower=lower, upper=upper)
        previous_ytd = ytd_history.get((fy, quarter - 1, tag))
        if current_ytd is None or previous_ytd is None:
            return None, current_ytd, None
        return current_ytd - previous_ytd, current_ytd, "YTD_MINUS_PRIOR_YTD"

    annual = _longest_duration_value(rows, tag=tag, end=end, lower=300, upper=380)
    previous = [quarter_history.get((fy, q, tag)) for q in (1, 2, 3)]
    if annual is None or any(value is None for value in previous):
        return None, annual, None
    return annual - sum(float(value) for value in previous if value is not None), annual, "FY_MINUS_Q1_Q2_Q3"


def _first_available(
    values: Mapping[str, float | None], precedence: Iterable[str]
) -> tuple[str | None, float | None]:
    for tag in precedence:
        value = values.get(tag)
        if value is not None:
            return tag, float(value)
    return None, None


def _feature_signals(
    feature_row: Mapping[str, Any], prior_features: Mapping[tuple[int, int, str], float]
) -> list[dict[str, Any]]:
    fy = int(feature_row["fiscal_year"])
    quarter = int(feature_row["fiscal_quarter"])
    signals: list[dict[str, Any]] = []
    for spec in XBRL_HYPOTHESES:
        current = feature_row.get(spec.feature)
        prior = prior_features.get((fy - 1, quarter, spec.feature))
        if current is None or prior is None:
            continue
        delta = float(current) - float(prior)
        if delta == 0:
            continue
        matches = delta > 0 if spec.delta_rule.endswith(">0") else delta < 0
        if matches:
            signals.append(
                {
                    "candidate_id": spec.candidate_id,
                    "direction": spec.direction,
                    "feature": spec.feature,
                    "current_feature": float(current),
                    "prior_year_feature": float(prior),
                    "yoy_delta": delta,
                }
            )
    return signals


def reconstruct_issuer_quarters(
    *,
    issuer_cik: str,
    entity_name: str,
    accession_rows: Iterable[tuple[dict[str, Any], tuple[dict[str, Any], ...]]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Reconstruct first-public PIT quarterly features from exact original accessions."""
    ytd_history: dict[tuple[int, int, str], float] = {}
    quarter_history: dict[tuple[int, int, str], float] = {}
    feature_history: dict[tuple[int, int, str], float] = {}
    asset_history: list[tuple[date, float, str]] = []
    seen_fiscal_periods: set[tuple[int, int]] = set()
    output: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()

    ordered = sorted(
        accession_rows,
        key=lambda item: (
            str(item[0].get("acceptance_datetime") or ""),
            str(item[0].get("accession_number") or ""),
        ),
    )
    for metadata, rows in ordered:
        form = str(metadata.get("form") or "")
        filing_date = _as_date(metadata.get("filing_date"))
        if form not in _ALLOWED_FORMS or filing_date is None:
            diagnostics["invalid_metadata"] += 1
            continue
        period = _current_period(rows, filing_date=filing_date, form=form)
        if period is None:
            diagnostics["period_identity_missing"] += 1
            continue
        period_end, fy, quarter = period
        fiscal_key = (fy, quarter)
        if fiscal_key in seen_fiscal_periods:
            diagnostics["later_same_fiscal_period_accessions_excluded"] += 1
            continue
        decision = _decision_session(str(metadata.get("acceptance_datetime") or ""))

        lagged_assets: float | None = None
        lagged_asset_end: date | None = None
        for asset_end, asset_value, _ in reversed(asset_history):
            if asset_end < period_end and 0 < (period_end - asset_end).days <= 200 and asset_value > 0:
                lagged_assets = asset_value
                lagged_asset_end = asset_end
                break

        tag_values: dict[str, float | None] = {}
        tag_methods: dict[str, str | None] = {}
        pending_ytd: dict[tuple[int, int, str], float] = {}
        pending_quarters: dict[tuple[int, int, str], float] = {}
        for tag in _FLOW_TAGS:
            quarter_value, ytd_value, method = _flow_quarter_value(
                rows,
                tag=tag,
                end=period_end,
                fy=fy,
                quarter=quarter,
                ytd_history=ytd_history,
                quarter_history=quarter_history,
            )
            tag_values[tag] = quarter_value
            tag_methods[tag] = method
            if ytd_value is not None:
                pending_ytd[(fy, quarter, tag)] = float(ytd_value)
            if quarter_value is not None:
                pending_quarters[(fy, quarter, tag)] = float(quarter_value)

        direct_gross = tag_values.get("GrossProfit")
        revenue_tag, revenue = _first_available(tag_values, XBRL_REVENUE_TAG_PRECEDENCE)
        cost_tag, cost = _first_available(tag_values, XBRL_COST_TAG_PRECEDENCE)
        if direct_gross is not None:
            gross_profit = float(direct_gross)
            gross_method = "DIRECT_GROSS_PROFIT"
        elif revenue is not None and cost is not None:
            gross_profit = revenue - cost
            gross_method = "REVENUE_MINUS_COST"
        else:
            gross_profit = None
            gross_method = None

        net_income = tag_values.get("NetIncomeLoss")
        cash_flow = tag_values.get("NetCashProvidedByUsedInOperatingActivities")
        features: dict[str, float | None] = {
            "gross_profitability": None,
            "cash_profitability": None,
            "accrual_intensity": None,
        }
        if lagged_assets is not None and lagged_assets > 0:
            if gross_profit is not None:
                features["gross_profitability"] = float(gross_profit) / lagged_assets
            if cash_flow is not None:
                features["cash_profitability"] = float(cash_flow) / lagged_assets
            if net_income is not None and cash_flow is not None:
                features["accrual_intensity"] = (
                    float(net_income) - float(cash_flow)
                ) / lagged_assets

        feature_row: dict[str, Any] = {
            "contract_version": XBRL_PREDICTOR_CONTRACT,
            "scientific_fingerprint": XBRL_SCIENTIFIC_FINGERPRINT,
            "issuer_cik": issuer_cik,
            "entity_name": entity_name,
            "accession_number": metadata.get("accession_number"),
            "filing_date": filing_date.isoformat(),
            "acceptance_datetime": metadata.get("acceptance_datetime"),
            "decision_session": decision.isoformat(),
            "form": form,
            "fiscal_year": fy,
            "fiscal_quarter": quarter,
            "period_end": period_end.isoformat(),
            "lagged_asset_end": lagged_asset_end.isoformat() if lagged_asset_end else None,
            "lagged_assets": lagged_assets,
            "gross_profit": gross_profit,
            "gross_profit_method": gross_method,
            "gross_profit_source_tag": "GrossProfit" if direct_gross is not None else None,
            "revenue_source_tag": revenue_tag,
            "cost_source_tag": cost_tag,
            "net_income": net_income,
            "operating_cash_flow": cash_flow,
            "tag_methods": tag_methods,
            **features,
        }
        feature_row["signals"] = _feature_signals(feature_row, feature_history)
        output.append(feature_row)

        seen_fiscal_periods.add(fiscal_key)
        for key, value in pending_ytd.items():
            ytd_history.setdefault(key, value)
        for key, value in pending_quarters.items():
            quarter_history.setdefault(key, value)
        for feature_name, value in features.items():
            if value is not None:
                feature_history.setdefault((fy, quarter, feature_name), float(value))

        current_assets = _instant_value(rows, tag="Assets", end=period_end)
        if current_assets is not None and current_assets > 0:
            asset_history.append(
                (period_end, float(current_assets), str(metadata.get("accession_number") or ""))
            )
            asset_history.sort(key=lambda item: (item[0], item[2]))

    diagnostics["quarter_rows"] = len(output)
    diagnostics["signal_rows_before_identity"] = sum(len(row.get("signals") or []) for row in output)
    return output, dict(sorted(diagnostics.items()))


class XBRLPredictorBuilder:
    """Build exact-accession PIT XBRL signals before any market outcome is joined."""

    def __init__(
        self,
        settings: AtlasSettings,
        companyfacts_client: SECXBRLCompanyFactsClient,
        submissions_client: SECXBRLPITMetadataClient,
        reference_provider: MassiveCIKPITReferenceProvider,
    ) -> None:
        self.settings = settings
        self.companyfacts_client = companyfacts_client
        self.submissions_client = submissions_client
        self.reference_provider = reference_provider
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.cache_root = self.provider_root / XBRL_PREDICTOR_CACHE_RELATIVE
        self.source_reads: Counter[str] = Counter()
        self.cache_hits: Counter[str] = Counter()

    def _load_feasibility(self) -> dict[str, Any]:
        path = self.derived_root / XBRL_REPORT_RELATIVE
        if not path.is_file():
            raise XBRLPredictorError(f"accepted feasibility report is missing: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise XBRLPredictorError("accepted feasibility report root is invalid")
        actual = accepted_feasibility_evidence_fingerprint(report)
        if actual != XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT:
            raise XBRLPredictorError(f"accepted feasibility evidence fingerprint differs: {actual}")
        sample = report.get("sample_ciks")
        if not isinstance(sample, list) or len(sample) != 200:
            raise XBRLPredictorError("accepted feasibility sample is not exactly 200 CIKs")
        return report

    def _cached_companyfacts(self, cik: str) -> dict[str, Any]:
        path = self.cache_root / "companyfacts" / f"{cik}.json"
        if path.is_file():
            self.cache_hits["companyfacts"] += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            if _normalize_cik(value.get("issuer_cik")) != cik:
                raise XBRLPredictorError(f"cached Company Facts CIK mismatch: {path}")
            return value
        self.source_reads["companyfacts"] += 1
        document = self.companyfacts_client.company_facts(cik=cik)
        entries = [
            row
            for row in _extract_relevant_entries(document)
            if str(row.get("unit") or "") == "USD"
        ]
        value = {
            "issuer_cik": document.issuer_cik,
            "entity_name": document.entity_name,
            "source_url": document.source_url,
            "source_sha256": document.source_sha256,
            "entries_sha256": _sha256_text(
                "".join(_canonical_json(row) + "\n" for row in entries)
            ),
            "entries": entries,
        }
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return value

    @staticmethod
    def _accession_groups(
        entries: Iterable[dict[str, Any]],
    ) -> list[tuple[str, str, str, tuple[dict[str, Any], ...]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in entries:
            accession = str(row.get("accn") or "").strip()
            if accession:
                grouped[accession].append(dict(row))
        result: list[tuple[str, str, str, tuple[dict[str, Any], ...]]] = []
        for accession, rows in grouped.items():
            filing_dates = {str(row.get("filed") or "") for row in rows}
            forms = {str(row.get("form") or "") for row in rows}
            if len(filing_dates) != 1 or len(forms) != 1:
                continue
            filing_date = next(iter(filing_dates))
            form = next(iter(forms))
            if form in _ALLOWED_FORMS:
                result.append((accession, filing_date, form, tuple(rows)))
        result.sort(key=lambda item: (item[1], item[0]))
        return result

    def _cached_metadata_batch(
        self,
        *,
        cik: str,
        groups: list[tuple[str, str, str, tuple[dict[str, Any], ...]]],
    ) -> tuple[dict[str, dict[str, Any]], int]:
        requests = [
            {"accession_number": accession, "filing_date": filing_date, "form": form}
            for accession, filing_date, form, _ in groups
        ]
        request_hash = _sha256_text(_canonical_json(requests))
        path = self.cache_root / "submissions" / f"{cik}.json"
        if path.is_file():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("issuer_cik") == cik and cached.get("request_sha256") == request_hash:
                records = cached.get("records")
                if isinstance(records, list):
                    self.cache_hits["submissions_batch"] += 1
                    return {
                        str(row["accession_number"]): dict(row)
                        for row in records
                        if isinstance(row, dict) and row.get("accession_number")
                    }, int(cached.get("metadata_failures", 0))

        resolved: dict[str, dict[str, Any]] = {}
        failures = 0
        try:
            self.source_reads["submissions_batch"] += 1
            records = self.submissions_client.filing_metadata_many(cik=cik, requests=requests)
            resolved = {record.accession_number: asdict(record) for record in records}
        except Exception:
            # A bounded fallback preserves accession-level fail-closed behavior for
            # the occasional problematic historical record without returning to a
            # root submissions request for every accession on the normal path.
            for accession, filing_date, form, _ in groups:
                try:
                    self.source_reads["submissions_fallback"] += 1
                    record = self.submissions_client.filing_metadata(
                        cik=cik,
                        accession_number=accession,
                        filing_date=filing_date,
                        allowed_forms=(form,),
                    )
                    resolved[accession] = asdict(record)
                except Exception:
                    failures += 1
        value = {
            "issuer_cik": cik,
            "request_sha256": request_hash,
            "requested_accessions": len(requests),
            "resolved_accessions": len(resolved),
            "metadata_failures": failures,
            "records": [resolved[key] for key in sorted(resolved)],
        }
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return resolved, failures

    def _cached_reference(self, *, cik: str, decision: date) -> list[dict[str, Any]]:
        path = self.cache_root / "massive_reference" / decision.isoformat() / f"{cik}.json"
        if path.is_file():
            self.cache_hits["massive_reference"] += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("issuer_cik") != cik or value.get("as_of_date") != decision.isoformat():
                raise XBRLPredictorError(f"cached Massive identity mismatch: {path}")
            rows = value.get("rows")
            if not isinstance(rows, list):
                raise XBRLPredictorError(f"cached Massive rows invalid: {path}")
            return [dict(row) for row in rows if isinstance(row, dict)]
        self.source_reads["massive_reference"] += 1
        rows = self.reference_provider.tradable_common_stock_snapshot(cik=cik, as_of_date=decision)
        value = {
            "issuer_cik": cik,
            "as_of_date": decision.isoformat(),
            "identity_rule": "EXACT_CIK_DATE_ACTIVE_TRUE_TYPE_CS",
            "rows": rows,
            "rows_sha256": _sha256_text(
                "".join(_canonical_json(row) + "\n" for row in rows)
            ),
        }
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return rows

    def run(self, *, progress_callback: Any | None = None) -> dict[str, Any]:
        if xbrl_scientific_fingerprint() != XBRL_SCIENTIFIC_FINGERPRINT:
            raise XBRLPredictorError("frozen XBRL scientific policy fingerprint drifted")
        feasibility = self._load_feasibility()
        sample_ciks = [_normalize_cik(value) for value in feasibility["sample_ciks"]]
        source_start = date.fromisoformat(XBRL_PREDICTOR_SOURCE_START)
        source_cutoff = date.fromisoformat(XBRL_PREDICTOR_SOURCE_CUTOFF)
        governed_start = date.fromisoformat(XBRL_PERFORMANCE_SIGNAL_START)
        development_last = date.fromisoformat(XBRL_DEVELOPMENT_LAST_SIGNAL)
        protected_start = date.fromisoformat(XBRL_PROTECTED_START)
        protected_last = date.fromisoformat(XBRL_PROTECTED_LAST_SIGNAL)

        predictor_rows: list[dict[str, Any]] = []
        issuer_diagnostics: list[dict[str, Any]] = []
        identity_statuses: Counter[str] = Counter()
        for index, cik in enumerate(sample_ciks, start=1):
            try:
                source = self._cached_companyfacts(cik)
                entries = [
                    dict(row)
                    for row in source.get("entries", [])
                    if isinstance(row, dict)
                    and (filed := _as_date(row.get("filed"))) is not None
                    and source_start <= filed <= source_cutoff
                ]
                groups = self._accession_groups(entries)
                metadata_by_accession, metadata_failures = self._cached_metadata_batch(
                    cik=cik, groups=groups
                )
                accession_rows = [
                    (metadata_by_accession[accession], rows)
                    for accession, _, _, rows in groups
                    if accession in metadata_by_accession
                ]
                quarters, diagnostics = reconstruct_issuer_quarters(
                    issuer_cik=cik,
                    entity_name=str(source.get("entity_name") or ""),
                    accession_rows=accession_rows,
                )
                emitted = 0
                for quarter_row in quarters:
                    decision = _as_date(quarter_row.get("decision_session"))
                    signals = list(quarter_row.get("signals") or [])
                    if (
                        decision is None
                        or not signals
                        or decision < governed_start
                        or decision > protected_last
                    ):
                        continue
                    stage = (
                        "DEVELOPMENT"
                        if decision <= development_last
                        else "PROTECTED"
                        if protected_start <= decision <= protected_last
                        else "EMBARGO"
                    )
                    if stage == "EMBARGO":
                        continue
                    reference_rows = self._cached_reference(cik=cik, decision=decision)
                    identity = _resolve_identity(reference_rows, issuer_cik=cik, as_of_date=decision)
                    identity_statuses[str(identity["status"])] += 1
                    if identity["status"] != "UNAMBIGUOUS_PIT_INSTRUMENT":
                        continue
                    instrument = identity["instruments"][0]
                    for signal in signals:
                        predictor_rows.append(
                            {
                                **{key: value for key, value in quarter_row.items() if key != "signals"},
                                **signal,
                                "stage": stage,
                                "instrument_id": instrument["instrument_id"],
                                "ticker": instrument.get("ticker"),
                                "identity_quality": instrument.get("identity_quality"),
                                "primary_exchange": instrument.get("primary_exchange"),
                                "security_type": instrument.get("security_type"),
                            }
                        )
                        emitted += 1
                issuer_diagnostics.append(
                    {
                        "issuer_cik": cik,
                        "entity_name": source.get("entity_name"),
                        "accessions_requested": len(groups),
                        "accessions_reconciled": len(accession_rows),
                        "metadata_failures": metadata_failures,
                        "signals_emitted": emitted,
                        **diagnostics,
                    }
                )
            except Exception as exc:
                issuer_diagnostics.append(
                    {
                        "issuer_cik": cik,
                        "status": "ISSUER_FAILURE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if progress_callback is not None and (
                index == 1 or index % 10 == 0 or index == len(sample_ciks)
            ):
                progress_callback(
                    f"XBRL predictor progress: {index}/{len(sample_ciks)} "
                    f"signals={len(predictor_rows)} source_reads={sum(self.source_reads.values())}"
                )

        predictor_rows.sort(
            key=lambda row: (
                str(row.get("stage")),
                str(row.get("decision_session")),
                str(row.get("candidate_id")),
                str(row.get("instrument_id")),
                str(row.get("accession_number")),
            )
        )
        duplicate_keys = Counter(
            (
                str(row.get("candidate_id")),
                str(row.get("instrument_id")),
                str(row.get("decision_session")),
                str(row.get("accession_number")),
            )
            for row in predictor_rows
        )
        if any(count > 1 for count in duplicate_keys.values()):
            raise XBRLPredictorError(
                "XBRL predictor contains duplicate candidate/instrument/session/accession keys"
            )

        rows_text = "".join(_canonical_json(row) + "\n" for row in predictor_rows)
        rows_path = self.derived_root / XBRL_PREDICTOR_ROWS_RELATIVE
        atomic_write_text(rows_path, rows_text)
        candidate_counts = Counter(str(row["candidate_id"]) for row in predictor_rows)
        stage_counts = Counter(str(row["stage"]) for row in predictor_rows)
        report = {
            "contract_version": XBRL_PREDICTOR_CONTRACT,
            "scientific_fingerprint": XBRL_SCIENTIFIC_FINGERPRINT,
            "feasibility_report_sha256": sha256_file(self.derived_root / XBRL_REPORT_RELATIVE),
            "accepted_feasibility_evidence_fingerprint": accepted_feasibility_evidence_fingerprint(feasibility),
            "sample_size": len(sample_ciks),
            "candidate_counts": dict(sorted(candidate_counts.items())),
            "stage_counts": dict(sorted(stage_counts.items())),
            "predictor_rows": len(predictor_rows),
            "predictor_rows_sha256": _sha256_text(rows_text),
            "identity_status_counts": dict(sorted(identity_statuses.items())),
            "source_reads_performed": sum(self.source_reads.values()),
            "source_read_breakdown": dict(sorted(self.source_reads.items())),
            "cache_hits": dict(sorted(self.cache_hits.items())),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "feature_semantics": dict(XBRL_FEATURES),
            "gross_profit_rule": XBRL_GROSS_PROFIT_RULE,
            "yoy_rule": XBRL_YOY_RULE,
            "issuer_diagnostics": issuer_diagnostics,
            "predictor_rows_path": str(rows_path),
        }
        report_path = self.derived_root / XBRL_PREDICTOR_REPORT_RELATIVE
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
