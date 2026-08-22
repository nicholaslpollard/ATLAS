from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.features.historical_backfill_feature_promotion_stage import (
    GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
    GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION,
)
from packages.features.historical_backfill_replay import HistoricalBackfillFeatureReplayPreflight
from packages.features.partition_store import sha256_file

from .cumulative_foundation import _json
from .cumulative_lifecycle_integrity import CumulativeFoundationLifecycleAwareAuditor


GATE9C_RETAINED_STAGE_LINEAGE_BASIS = (
    "GATE9C_RETAINED_STAGE_YEAR_MANIFESTS_PLUS_REDERIVED_LIFECYCLE_EVENTS"
)


def transition_dates(rows: dict[date, dict[str, object]]) -> set[date]:
    """Return sessions whose accepted input state differs from the prior output state."""

    transitions: set[date] = set()
    prior_output: str | None = None
    for session in sorted(rows):
        row = rows[session]
        current_input = str(row["input_state_fingerprint"])
        if prior_output is not None and current_input != prior_output:
            transitions.add(session)
        prior_output = str(row["output_state_fingerprint"])
    return transitions


def transitions_are_lifecycle_backed(
    rows: dict[date, dict[str, object]],
    lifecycle_dates: set[date],
) -> tuple[bool, list[date]]:
    """Prove every non-adjacent state transition occurs on an accepted lifecycle-event date."""

    unbacked = sorted(transition_dates(rows) - lifecycle_dates)
    return not unbacked, unbacked


class CumulativeFoundationRetainedStageAuditor(CumulativeFoundationLifecycleAwareAuditor):
    """Use the retained Gate 9-C production-build proofs actually present after handoff.

    The optional candidate state-chain artifact is not part of the durable production
    handoff. Gate 9-C instead created production-native per-session manifests while
    independently replaying lifecycle state, then retained hash-bound per-year stage
    manifests after the staged feature/manifest/state directories were moved live.
    This auditor binds every production 1d manifest to those retained year proofs and
    independently re-derives lifecycle-event dates from Gate 4-C/Gate 7 evidence.
    """

    def _daily_state_chain(
        self,
        end_date: date,
    ) -> tuple[dict[date, dict[str, object]], dict[str, object]]:
        promotion_root = self._promotion_root()
        stage_root = promotion_root / "stage"
        report_path = promotion_root / "gate9c_stage_report.json"
        report = _json(report_path, "Gate 9-C retained stage report")

        year_records = report.get("year_manifests")
        if not isinstance(year_records, list):
            year_records = []

        lifecycle_preflight = HistoricalBackfillFeatureReplayPreflight(self.settings)
        lifecycle_events, lifecycle_counts = lifecycle_preflight._lifecycle_events()
        lifecycle_by_date: dict[date, int] = {}
        for event in lifecycle_events:
            event_date = event.get("event_date")
            if isinstance(event_date, date):
                normalized = event_date
            else:
                normalized = date.fromisoformat(str(event_date)[:10])
            if normalized <= end_date:
                lifecycle_by_date[normalized] = lifecycle_by_date.get(normalized, 0) + 1

        rows: dict[date, dict[str, object]] = {}
        duplicate_sessions = 0
        year_manifest_failures: list[str] = []
        checked_years = 0

        for year_record in year_records:
            if not isinstance(year_record, dict):
                year_manifest_failures.append("malformed year-manifest record")
                continue
            try:
                year = int(year_record["year"])
            except (KeyError, TypeError, ValueError):
                year_manifest_failures.append("year-manifest record lacks valid year")
                continue
            year_path = stage_root / "year_manifests" / f"{year:04d}.json"
            if not year_path.is_file():
                year_manifest_failures.append(f"{year}: retained stage year manifest missing")
                continue
            actual_sha = sha256_file(year_path)
            if actual_sha != str(year_record.get("sha256", "")):
                year_manifest_failures.append(f"{year}: retained stage year-manifest hash mismatch")
                continue
            payload = _json(year_path, f"Gate 9-C retained stage year manifest {year}")
            if payload.get("contract_version") != GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION:
                year_manifest_failures.append(f"{year}: retained stage year contract stale")
                continue
            if int(payload.get("year", -1)) != year:
                year_manifest_failures.append(f"{year}: retained stage year identity mismatch")
                continue
            sessions = payload.get("sessions")
            if not isinstance(sessions, list):
                year_manifest_failures.append(f"{year}: retained stage session list malformed")
                continue
            if int(payload.get("session_count", -1)) != len(sessions):
                year_manifest_failures.append(f"{year}: retained stage session count mismatch")
                continue
            if payload.get("output_state_fingerprint") != year_record.get(
                "output_state_fingerprint"
            ):
                year_manifest_failures.append(f"{year}: retained stage year-end state mismatch")
                continue

            checked_years += 1
            for session_record in sessions:
                if not isinstance(session_record, dict):
                    year_manifest_failures.append(f"{year}: malformed retained session record")
                    continue
                try:
                    session = date.fromisoformat(str(session_record["session_date"])[:10])
                except (KeyError, TypeError, ValueError):
                    year_manifest_failures.append(f"{year}: invalid retained session date")
                    continue
                if session < self._history_origin() or session > end_date:
                    continue
                if session in rows:
                    duplicate_sessions += 1
                    continue
                canonical = self.paths.canonical_file(Timeframe.DAY_1, session)
                source_sha = sha256_file(canonical) if canonical.is_file() else ""
                rows[session] = {
                    "session_date": session.isoformat(),
                    "input_state_fingerprint": str(
                        session_record.get("input_state_fingerprint", "")
                    ),
                    "output_state_fingerprint": str(
                        session_record.get("output_state_fingerprint", "")
                    ),
                    "lifecycle_event_count": int(lifecycle_by_date.get(session, 0)),
                    "source_sha256": source_sha,
                    "candidate_feature_sha256": str(
                        session_record.get("feature_sha256", "")
                    ),
                    "row_count": int(session_record.get("row_count", -1)),
                    "symbol_count": int(session_record.get("symbol_count", -1)),
                }

        lifecycle_dates = set(lifecycle_by_date)
        transition_set = transition_dates(rows)
        transitions_backed, unbacked_transitions = transitions_are_lifecycle_backed(
            rows,
            lifecycle_dates,
        )
        report_last = report.get("last_session")
        try:
            report_last_date = date.fromisoformat(str(report_last)[:10])
        except ValueError:
            report_last_date = date.min

        checks = {
            "stage_contract_current": report.get("contract_version")
            == GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
            "stage_report_pass": report.get("pass") is True,
            "stage_report_checks_all_true": bool(report.get("checks"))
            and all(bool(value) for value in dict(report.get("checks") or {}).values()),
            "stage_production_feature_writes_zero": int(
                report.get("production_feature_writes", -1)
            )
            == 0,
            "retained_year_manifests_present": bool(year_records),
            "retained_year_manifests_exact": not year_manifest_failures,
            "retained_years_checked": checked_years == len(year_records),
            "retained_sessions_unique": duplicate_sessions == 0,
            "retained_stage_covers_audit_end": report_last_date >= end_date,
            "lifecycle_evidence_present": bool(lifecycle_events),
            "state_transitions_lifecycle_backed": transitions_backed,
        }
        return rows, {
            "basis": GATE9C_RETAINED_STAGE_LINEAGE_BASIS,
            "report_path": str(report_path.resolve()),
            "report_sha256": sha256_file(report_path),
            "chain_path": None,
            "chain_sha256": None,
            "retained_year_manifest_count": len(year_records),
            "checked_year_manifest_count": checked_years,
            "year_manifest_failure_count": len(year_manifest_failures),
            "year_manifest_failure_samples": year_manifest_failures[:20],
            "lifecycle_event_count": len(lifecycle_events),
            "lifecycle_event_session_count": len(lifecycle_dates),
            "lifecycle_counts": lifecycle_counts,
            "state_transition_count": len(transition_set),
            "unbacked_state_transition_count": len(unbacked_transitions),
            "unbacked_state_transition_dates": [
                item.isoformat() for item in unbacked_transitions[:20]
            ],
            "checks": checks,
            "pass": all(checks.values()),
        }

    @staticmethod
    def _history_origin() -> date:
        return ALPACA_BACKFILL_START


from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
