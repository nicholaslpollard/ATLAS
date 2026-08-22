from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from typing import Any

import duckdb

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity import (
    AlpacaBackfillIdentityBuilder as RetainedEvidenceIdentityBuilder,
    AlpacaBackfillIdentityReport,
)


ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION = (
    "historical-backfill-identity-v2-observed-handoff-boundary"
)
MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS = 7
PROCESS_DATE_TIMING_REASONS = {
    "NEW_OBSERVED_BEFORE_CHANGE",
    "OLD_OBSERVED_AFTER_CHANGE",
    "OBSERVATION_OVERLAP",
}


def _clean_reason_set(value: object) -> set[str]:
    if value is None:
        return set()
    return {
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    }


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def classify_observed_handoff(row: dict[str, object]) -> dict[str, object]:
    """Refine one Gate 4 rename candidate using observed trading boundaries.

    Alpaca name-change ``process_date`` is retained as corroborating provider evidence,
    but it is not treated as the exact first trading date under the new literal ticker.
    Identity/graph blockers produced by the retained-evidence pass remain hard blockers.
    When both literals are observed, an automatic continuity candidate requires a
    non-overlapping handoff of no more than seven calendar days.
    """

    reasons = _clean_reason_set(row.get("review_reasons")) - PROCESS_DATE_TIMING_REASONS
    old_observed = bool(row.get("old_observed"))
    new_observed = bool(row.get("new_observed"))
    old_last = _as_date(row.get("old_last_date"))
    new_first = _as_date(row.get("new_first_date"))
    process_date = _as_date(row.get("event_date"))

    handoff_gap_calendar_days: int | None = None
    process_date_lag_from_new_start_days: int | None = None

    if process_date is not None and new_first is not None:
        process_date_lag_from_new_start_days = (process_date - new_first).days

    if old_observed and new_observed:
        if old_last is None or new_first is None:
            reasons.add("MISSING_OBSERVATION_BOUNDARY")
        elif old_last >= new_first:
            reasons.add("OBSERVATION_OVERLAP")
            handoff_gap_calendar_days = (new_first - old_last).days
        else:
            handoff_gap_calendar_days = (new_first - old_last).days
            if handoff_gap_calendar_days > MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS:
                reasons.add("OBSERVED_HANDOFF_GAP_EXCEEDS_7_DAYS")

    if reasons:
        status = "REVIEW_REQUIRED"
        safe_to_stitch = False
    elif old_observed and new_observed:
        status = "SAFE_STITCH_CANDIDATE"
        safe_to_stitch = True
    else:
        status = "CONTINUITY_EVIDENCE_ONLY"
        safe_to_stitch = False

    revised = dict(row)
    revised.update(
        {
            "status": status,
            "safe_to_stitch": safe_to_stitch,
            "review_reasons": ",".join(sorted(reasons)),
            "handoff_gap_calendar_days": handoff_gap_calendar_days,
            "process_date_lag_from_new_start_days": process_date_lag_from_new_start_days,
            "transition_boundary_policy": "OBSERVED_HANDOFF_MAX_7_CALENDAR_DAYS",
            "provider_event_date_role": "CORROBORATING_EVIDENCE_NOT_BAR_BOUNDARY",
        }
    )
    return revised


class AlpacaBackfillIdentityPolicyBuilder:
    """Gate 4-B wrapper that applies the observed-handoff continuity policy.

    The retained-evidence builder remains responsible for parsing and normalizing the
    immutable corporate-action pages. This layer refines only rename continuity triage;
    it never fetches provider data and never modifies production canonical history.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.evidence_builder = RetainedEvidenceIdentityBuilder(settings)

    def _load_rename_rows(self) -> list[dict[str, object]]:
        path = self.evidence_builder.rename_candidate_path
        if not path.is_file():
            raise RuntimeError(f"Gate 4 rename candidate artifact is missing: {path}")
        con = duckdb.connect(":memory:")
        try:
            frame = con.execute(
                "SELECT * FROM read_parquet(?) ORDER BY event_date NULLS LAST, "
                "old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
                [str(path)],
            ).fetchdf()
        finally:
            con.close()
        return frame.to_dict(orient="records")

    def run(self) -> AlpacaBackfillIdentityReport:
        base_report = self.evidence_builder.run()
        rows = [classify_observed_handoff(row) for row in self._load_rename_rows()]

        self.evidence_builder._write_parquet(
            self.evidence_builder.rename_candidate_path,
            rows,
            "event_date NULLS LAST, old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
        )

        safe = sum(1 for row in rows if row["status"] == "SAFE_STITCH_CANDIDATE")
        evidence_only = sum(
            1 for row in rows if row["status"] == "CONTINUITY_EVIDENCE_ONLY"
        )
        review = sum(1 for row in rows if row["status"] == "REVIEW_REQUIRED")
        gate3_sensitive = sum(
            1
            for row in rows
            if "GATE3_CASEFOLD_ANOMALY" in _clean_reason_set(row.get("review_reasons"))
        )
        actual_overlaps = sum(
            1
            for row in rows
            if "OBSERVATION_OVERLAP" in _clean_reason_set(row.get("review_reasons"))
        )
        long_gap_reviews = sum(
            1
            for row in rows
            if "OBSERVED_HANDOFF_GAP_EXCEEDS_7_DAYS"
            in _clean_reason_set(row.get("review_reasons"))
        )

        report = replace(
            base_report,
            contract_version=ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            safe_stitch_candidates=safe,
            continuity_evidence_only=evidence_only,
            rename_review_required=review,
            gate3_casefold_sensitive_candidates=gate3_sensitive,
        )

        payload: dict[str, Any] = asdict(report)
        payload["rename_handoff_policy"] = {
            "policy": "observed old-last/new-first boundary",
            "max_safe_handoff_calendar_days": MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS,
            "provider_event_date_role": "corroborating evidence, not exact bar boundary",
            "actual_observation_overlaps": actual_overlaps,
            "long_gap_review_required": long_gap_reviews,
        }
        atomic_write_text(
            self.evidence_builder.report_path,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
        return report
