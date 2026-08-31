from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from packages.backtesting.alpha_gate_finra_short_interest_pit_evidence_binding_repair import (
    FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256,
    FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT,
)
from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
    FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE,
    FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE,
)
from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    FINRA_SHORT_INTEREST_SELECTION_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_UNIQUE_INSTRUMENTS,
)
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


FINRA_SHORT_INTEREST_SOURCE_CLOSEOUT_PROBE_CONTRACT = (
    "alpha-gate-finra-short-interest-source-only-closeout-probe-v1-"
    "persisted-predictor-negative-no-provider-no-market-outcomes"
)
FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD = (
    "d312ec95752ab49a6fcbec18973faacb96d4aa89"
)
FINRA_SHORT_INTEREST_EXPECTED_PIT_REPORT_SHA256 = (
    "6dd2a84d397ae9669665d1a4a277abae61ded74876dc8e788b3a60a66719d8e6"
)
FINRA_SHORT_INTEREST_EXPECTED_PREDICTOR_ROWS = 19_343
FINRA_SHORT_INTEREST_EXPECTED_STAGE_COUNTS = {
    "DEVELOPMENT": 14_841,
    "PROTECTED": 4_502,
}
FINRA_SHORT_INTEREST_EXPECTED_CANDIDATE_COUNTS = {
    "rapid_short_build_crowded_short": 2_036,
    "rapid_short_build_non_crowded_short": 8_025,
    "rapid_short_cover_crowded_long": 1_257,
    "rapid_short_cover_non_crowded_long": 8_025,
}
FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES = {
    "rapid_short_build_crowded_short": {
        "development_min_rows": True,
        "development_min_signal_sessions": True,
        "development_min_unique_instruments": True,
        "protected_min_rows": True,
        "protected_min_signal_sessions": True,
        "protected_min_unique_instruments": True,
    },
    "rapid_short_build_non_crowded_short": {
        "development_min_rows": True,
        "development_min_signal_sessions": True,
        "development_min_unique_instruments": True,
        "protected_min_rows": True,
        "protected_min_signal_sessions": True,
        "protected_min_unique_instruments": True,
    },
    "rapid_short_cover_crowded_long": {
        "development_min_rows": True,
        "development_min_signal_sessions": True,
        "development_min_unique_instruments": True,
        "protected_min_rows": False,
        "protected_min_signal_sessions": True,
        "protected_min_unique_instruments": True,
    },
    "rapid_short_cover_non_crowded_long": {
        "development_min_rows": True,
        "development_min_signal_sessions": True,
        "development_min_unique_instruments": True,
        "protected_min_rows": True,
        "protected_min_signal_sessions": True,
        "protected_min_unique_instruments": True,
    },
}
FINRA_SHORT_INTEREST_EXPECTED_DIAGNOSTICS = {
    "EXCLUDED_REVISION_FLAG": 4_913,
    "EXCLUDED_STOCK_SPLIT_FLAG": 2_502,
    "IDENTITY_CONTINUITY_MISMATCH": 287,
    "NON_EXCHANGE_LISTED": 1_029_878,
    "NO_OR_AMBIGUOUS_DECISION_IDENTITY": 2_569,
    "NO_OR_AMBIGUOUS_SETTLEMENT_IDENTITY": 684_139,
    "OUTSIDE_FROZEN_CHANGE_TAILS": 457_181,
    "SAMPLED_rapid_short_build_crowded_short": 2_036,
    "SAMPLED_rapid_short_build_non_crowded_short": 8_025,
    "SAMPLED_rapid_short_cover_crowded_long": 1_257,
    "SAMPLED_rapid_short_cover_non_crowded_long": 8_025,
}
FINRA_SHORT_INTEREST_EXPECTED_FINRA_SOURCE_FILES = 116
FINRA_SHORT_INTEREST_EXPECTED_MASSIVE_SNAPSHOTS = 232
FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE = "rapid_short_cover_crowded_long"
FINRA_SHORT_INTEREST_UNDERPOWERED_GATE = "protected_min_rows"


class FINRAShortInterestSourceCloseoutProbeError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FINRAShortInterestSourceCloseoutProbeError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FINRAShortInterestSourceCloseoutProbeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise FINRAShortInterestSourceCloseoutProbeError(f"{label} must be a JSON object")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def finra_source_only_disposition(
    source_gates: Mapping[str, Mapping[str, bool]],
    *,
    target_outcome_rows_read: int,
    protected_return_rows_read: int,
    protected_holdout_consumed: bool,
) -> str:
    if target_outcome_rows_read != 0:
        raise FINRAShortInterestSourceCloseoutProbeError(
            "source-only closeout is forbidden after development outcome reads"
        )
    if protected_return_rows_read != 0 or protected_holdout_consumed:
        raise FINRAShortInterestSourceCloseoutProbeError(
            "source-only closeout is forbidden after protected-return consumption"
        )
    failed = sorted(
        (candidate_id, gate)
        for candidate_id, gates in source_gates.items()
        for gate, passed in gates.items()
        if passed is not True
    )
    if failed == [
        (FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE, FINRA_SHORT_INTEREST_UNDERPOWERED_GATE)
    ]:
        return "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT"
    if not failed:
        return "SOURCE_ONLY_PASS_NOT_CLOSEABLE"
    raise FINRAShortInterestSourceCloseoutProbeError(
        "unexpected source-only gate failure set: " + repr(failed)
    )


def _zero_authority_checks(report: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "target_outcomes_unread": int(report.get("target_outcome_rows_read", -1)) == 0,
        "protected_returns_unread": int(report.get("protected_return_rows_read", -1)) == 0,
        "protected_holdout_unconsumed": report.get("protected_holdout_consumed") is False,
        "provider_writes_zero": int(report.get("provider_writes_performed", -1)) == 0,
        "broker_reads_zero": int(report.get("broker_reads_performed", -1)) == 0,
        "broker_writes_zero": int(report.get("broker_writes_performed", -1)) == 0,
        "orders_zero": int(report.get("order_writes_performed", -1)) == 0,
        "paper_zero": int(report.get("paper_submits_performed", -1)) == 0,
        "live_zero": int(report.get("live_writes_performed", -1)) == 0,
        "automation_zero": int(report.get("automation_writes_performed", -1)) == 0,
        "automatic_broker_failover_false": report.get("automatic_broker_failover") is False,
        "phase33_authority_false": report.get("phase33_signal_to_trade_authority") is False,
    }


def collect_finra_source_only_closeout_evidence(settings: AtlasSettings) -> dict[str, Any]:
    """Validate persisted predictor artifacts only; perform no provider or market-outcome reads."""
    derived_root = settings.resolved_path(settings.data.paths.derived)
    report_path = derived_root / FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE
    rows_path = derived_root / FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE
    report = _read_json(report_path, "FINRA predictor report")
    if not rows_path.is_file():
        raise FINRAShortInterestSourceCloseoutProbeError(
            f"missing FINRA predictor rows: {rows_path}"
        )

    predictor_report_sha256 = sha256_file(report_path)
    predictor_rows_sha256 = sha256_file(rows_path)
    stage_candidate_counts: Counter[str] = Counter()
    sessions: dict[tuple[str, str], set[str]] = defaultdict(set)
    instruments: dict[tuple[str, str], set[str]] = defaultdict(set)
    row_count = 0
    with rows_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise FINRAShortInterestSourceCloseoutProbeError(
                    f"invalid predictor row JSON at line {line_number}"
                ) from exc
            if not isinstance(row, dict):
                raise FINRAShortInterestSourceCloseoutProbeError(
                    f"predictor row {line_number} is not an object"
                )
            if row.get("scientific_fingerprint") != FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT:
                raise FINRAShortInterestSourceCloseoutProbeError(
                    f"predictor row {line_number} scientific fingerprint drifted"
                )
            candidate_id = str(row.get("candidate_id") or "")
            stage = str(row.get("stage") or "")
            key = (candidate_id, stage)
            stage_candidate_counts[f"{candidate_id}|{stage}"] += 1
            sessions[key].add(str(row.get("decision_session") or ""))
            instruments[key].add(str(row.get("instrument_id") or ""))
            row_count += 1

    observed_source_gates = report.get("source_only_gates")
    if not isinstance(observed_source_gates, dict):
        raise FINRAShortInterestSourceCloseoutProbeError("source-only gate matrix is missing")

    disposition = finra_source_only_disposition(
        observed_source_gates,
        target_outcome_rows_read=int(report.get("target_outcome_rows_read", -1)),
        protected_return_rows_read=int(report.get("protected_return_rows_read", -1)),
        protected_holdout_consumed=bool(report.get("protected_holdout_consumed")),
    )

    underpowered_key = (FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE, "PROTECTED")
    underpowered_protected = {
        "event_rows": stage_candidate_counts[
            f"{FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE}|PROTECTED"
        ],
        "signal_sessions": len(sessions[underpowered_key]),
        "unique_instruments": len(instruments[underpowered_key]),
        "minimum_event_rows": FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
        "minimum_signal_sessions": FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
        "minimum_unique_instruments": FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    }

    checks: dict[str, bool] = {
        "predictor_contract_exact": report.get("contract_version") == FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
        "scientific_fingerprint_exact": report.get("scientific_fingerprint") == FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "predictor_status_exact": report.get("status") == "SOURCE_ONLY_PREDICTOR_FAIL",
        "predictor_pass_false": report.get("pass") is False,
        "predictor_rows_exact": int(report.get("predictor_rows", -1)) == FINRA_SHORT_INTEREST_EXPECTED_PREDICTOR_ROWS == row_count,
        "stage_counts_exact": report.get("stage_counts") == FINRA_SHORT_INTEREST_EXPECTED_STAGE_COUNTS,
        "candidate_counts_exact": report.get("candidate_counts") == FINRA_SHORT_INTEREST_EXPECTED_CANDIDATE_COUNTS,
        "source_gate_matrix_exact": observed_source_gates == FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES,
        "diagnostics_exact": report.get("diagnostics") == FINRA_SHORT_INTEREST_EXPECTED_DIAGNOSTICS,
        "finra_source_files_exact": int(report.get("finra_source_files_read", -1)) == FINRA_SHORT_INTEREST_EXPECTED_FINRA_SOURCE_FILES,
        "massive_snapshots_exact": int(report.get("massive_reference_snapshots_read", -1)) == FINRA_SHORT_INTEREST_EXPECTED_MASSIVE_SNAPSHOTS,
        "pit_report_sha_exact": report.get("accepted_pit_audit_report_sha256") == FINRA_SHORT_INTEREST_EXPECTED_PIT_REPORT_SHA256,
        "feasibility_parent_sha_exact": report.get("accepted_feasibility_report_sha256") == FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256,
        "semantic_binding_exact": report.get("pit_evidence_binding_repair_fingerprint") == FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT,
        "predictor_rows_sha_bound": report.get("predictor_rows_sha256") == predictor_rows_sha256,
        "underpowered_rows_below_frozen_min": 0 <= underpowered_protected["event_rows"] < FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
        "underpowered_sessions_meet_frozen_min": underpowered_protected["signal_sessions"] >= FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
        "underpowered_instruments_meet_frozen_min": underpowered_protected["unique_instruments"] >= FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
        "negative_disposition_exact": disposition == "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
    }
    checks.update(_zero_authority_checks(report))
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FINRAShortInterestSourceCloseoutProbeError(
            "FINRA source-only closeout evidence probe failed: " + ", ".join(failed)
        )

    stage_candidate = dict(sorted(stage_candidate_counts.items()))
    evidence_payload = {
        "probe_contract": FINRA_SHORT_INTEREST_SOURCE_CLOSEOUT_PROBE_CONTRACT,
        "accepted_source_target_head": FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
        "scientific_fingerprint": FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "pit_evidence_binding_repair_fingerprint": FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT,
        "predictor_report_sha256": predictor_report_sha256,
        "predictor_rows_sha256": predictor_rows_sha256,
        "predictor_rows": row_count,
        "stage_counts": FINRA_SHORT_INTEREST_EXPECTED_STAGE_COUNTS,
        "candidate_counts": FINRA_SHORT_INTEREST_EXPECTED_CANDIDATE_COUNTS,
        "candidate_stage_counts": stage_candidate,
        "underpowered_candidate": FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE,
        "underpowered_protected_source": underpowered_protected,
        "failing_gate": FINRA_SHORT_INTEREST_UNDERPOWERED_GATE,
        "finra_source_files_read": FINRA_SHORT_INTEREST_EXPECTED_FINRA_SOURCE_FILES,
        "massive_reference_snapshots_read": FINRA_SHORT_INTEREST_EXPECTED_MASSIVE_SNAPSHOTS,
        "accepted_pit_audit_report_sha256": FINRA_SHORT_INTEREST_EXPECTED_PIT_REPORT_SHA256,
        "disposition": disposition,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "phase33_signal_to_trade_authority": False,
    }
    return {
        **evidence_payload,
        "evidence_fingerprint": _fingerprint(evidence_payload),
        "checks": checks,
        "report_path": str(report_path),
        "rows_path": str(rows_path),
    }
