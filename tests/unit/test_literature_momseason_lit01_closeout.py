from __future__ import annotations

from copy import deepcopy

import pytest

from packages.backtesting.literature_momseason_development import (
    MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
    MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE,
)
from packages.backtesting.literature_momseason_development_source_diagnostic import (
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
)
from packages.backtesting.literature_momseason_lit01_closeout import (
    LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS,
    build_lit01_closeout_report,
)


def _diagnostic() -> dict[str, object]:
    return {
        "status": LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
        "freeze_fingerprint": MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
        "holdings_fingerprint": "holdings-fp",
        "target_plan_fingerprint": "target-fp",
        "holdings_rows": 41056,
        "target_plan_rows": 51666,
        "missing_target_units": 0,
        "unavailable_plan_rows": 201,
        "unavailable_source_keys": 199,
        "unavailable_status_counts": {"ZERO_BAR": 201},
        "blocked_holdings": 237,
        "blocked_holdings_by_hypothesis": {
            "momseason_short_year1": 130,
            "momseason_years2_5": 107,
        },
        "provider_reads_performed": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
    }


def _development() -> dict[str, object]:
    return {
        "status": MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE,
        "freeze_fingerprint": MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
        "plan": {
            "holdings_fingerprint": "holdings-fp",
            "target_plan_fingerprint": "target-fp",
            "holdings_rows": 41056,
            "target_plan_rows": 51666,
        },
        "evaluation": {
            "source_complete": False,
            "complete_holding_returns": 40819,
            "unavailable_holding_returns": 237,
            "family_finalist": None,
            "finalist_hypotheses": [],
        },
        "development_outcome_rows_read": 40819,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
    }


def test_valid_closeout_is_source_inconclusive_not_alpha_negative() -> None:
    report = build_lit01_closeout_report(_diagnostic(), _development())

    assert report["status"] == LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS
    assert report["scientific_classification"] == "SOURCE_INTEGRITY_INCONCLUSIVE"
    assert report["economic_signal_classification"] == "NOT_REACHED"
    assert report["alpha_rejection"] is False
    assert report["alpha_support"] is False
    assert report["family_finalist"] is None
    assert report["finalist_hypotheses"] == []
    assert report["lit01_inference_performed"] is False
    assert report["lit01_source_contract_changed"] is False
    assert report["development_outcomes_opened"] is True
    assert report["development_complete_holding_returns"] == 40819
    assert report["development_unavailable_holding_returns"] == 237
    assert report["unavailable_provider_source_keys"] == 199
    assert report["unavailable_plan_rows"] == 201
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["provider_reads_performed"] == 0
    assert report["phase33_signal_to_trade_authority"] is False
    assert report["production_authority"] is False
    assert len(str(report["closeout_fingerprint"])) == 64


def test_closeout_rejects_complete_evaluation() -> None:
    development = _development()
    development["evaluation"] = {**development["evaluation"], "source_complete": True}
    with pytest.raises(RuntimeError, match="complete evaluation"):
        build_lit01_closeout_report(_diagnostic(), development)


def test_closeout_rejects_protected_consumption() -> None:
    development = _development()
    development["protected_holdout_consumed"] = True
    with pytest.raises(RuntimeError, match="consumed the protected holdout"):
        build_lit01_closeout_report(_diagnostic(), development)


def test_closeout_rejects_protected_return_read() -> None:
    diagnostic = _diagnostic()
    diagnostic["protected_return_rows_read"] = 1
    with pytest.raises(RuntimeError, match="safety field is nonzero"):
        build_lit01_closeout_report(diagnostic, _development())


def test_closeout_rejects_fingerprint_mismatch() -> None:
    diagnostic = _diagnostic()
    diagnostic["holdings_fingerprint"] = "changed"
    with pytest.raises(RuntimeError, match="holdings fingerprint mismatch"):
        build_lit01_closeout_report(diagnostic, _development())


def test_closeout_rejects_no_unavailable_rows() -> None:
    diagnostic = _diagnostic()
    diagnostic["unavailable_plan_rows"] = 0
    with pytest.raises(RuntimeError, match="source incompleteness"):
        build_lit01_closeout_report(diagnostic, _development())


def test_closeout_rejects_positive_family_finalist() -> None:
    development = _development()
    evaluation = deepcopy(development["evaluation"])
    evaluation["family_finalist"] = True
    evaluation["finalist_hypotheses"] = ["momseason_short_year1"]
    development["evaluation"] = evaluation
    with pytest.raises(RuntimeError, match="positive family-finalist"):
        build_lit01_closeout_report(_diagnostic(), development)


def test_closeout_rejects_nonempty_finalist_hypotheses() -> None:
    development = _development()
    evaluation = deepcopy(development["evaluation"])
    evaluation["family_finalist"] = False
    evaluation["finalist_hypotheses"] = ["momseason_years2_5"]
    development["evaluation"] = evaluation
    with pytest.raises(RuntimeError, match="nonempty finalist hypotheses"):
        build_lit01_closeout_report(_diagnostic(), development)


def test_closeout_rejects_blocked_return_count_mismatch() -> None:
    diagnostic = _diagnostic()
    diagnostic["blocked_holdings"] = 236
    with pytest.raises(RuntimeError, match="blocked-return count mismatch"):
        build_lit01_closeout_report(diagnostic, _development())
