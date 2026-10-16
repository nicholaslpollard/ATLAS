from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_input_packet_v1 import FEATURE_CUTOFF, requested_prior_sessions
from packages.data import options_native_spy_prior_variance_sensitivity_v1 as subject
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT
from scripts import inspect_options_native_spy_prior_variance_v1 as cli


def seal(path: Path, value: dict) -> tuple[str, str]:
    value.pop("report_fingerprint", None)
    fp = _fingerprint(value)
    value["report_fingerprint"] = fp
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest(), fp


def invented(tmp_path: Path):
    """Invent two exact-shaped reports, not accepted historic market evidence."""
    calendar = get_market_calendar("XNYS")
    rows = []
    dates = requested_prior_sessions()
    for i, day in enumerate(dates):
        end = calendar.regular_open_close(day)[1]
        value = Decimal(300 + i)
        if day.isoformat() == "2019-12-19":
            value = Decimal("320.91")
        if day.isoformat() == "2019-12-20":
            value = Decimal("320.95")
        rows.append({
            "role": "PRIOR_REGULAR_CLOSE", "session_date": day.isoformat(),
            "interval_start_utc": (end - timedelta(minutes=1)).isoformat(),
            "interval_end_utc": end.isoformat(),
            "state": "EXACT_CACHED_MINUTE_PRESENT",
            "raw_close": str(value), "retained_daily_close": str(value),
            "minute_minus_daily": "0",
            "historical_available_at_utc": None, "interval_end_is_publication_proof": False,
            "economic_return_qualified": False, "pilot_eligible": False,
        })
    rows.append({
        "role": "DECISION_SPOT", "session_date": "2020-01-06",
        "interval_start_utc": (FEATURE_CUTOFF - timedelta(minutes=1)).isoformat(),
        "interval_end_utc": FEATURE_CUTOFF.isoformat(),
        "state": "EXACT_CACHED_MINUTE_PRESENT", "raw_close": "321.60",
        "historical_available_at_utc": None, "pilot_eligible": False,
    })
    first = {
        "action_type": "cash_dividends", "effective_date_state": "RECORDED_DATES_REQUIRE_TYPE_SPECIFIC_REVIEW",
        "historical_available_at_utc": None, "point_in_time_qualified": False,
        "source_page_index": 12, "source_record_index": 15, "manifest_recorded_source_page_sha256": "a" * 64,
        "payload": {
            "symbol": "SPY", "special": False, "ex_date": "2019-12-20",
            "rate": "1.569992", "process_date": "2019-12-20",
        },
    }
    future = {
        "action_type": "cash_dividends", "effective_date_state": "RECORDED_DATES_REQUIRE_TYPE_SPECIFIC_REVIEW",
        "historical_available_at_utc": None, "point_in_time_qualified": False,
        "source_page_index": 14, "source_record_index": 17, "manifest_recorded_source_page_sha256": "b" * 64,
        "payload": {
            "symbol": "SPY", "special": False, "ex_date": "2020-03-20",
            "rate": "1.405559", "process_date": "2020-04-30",
        },
    }
    stock = {
        "contract": "atlas-options-native-cached-stock-input-review-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(),
        "requested_minute_observations": 22, "present_minute_observations": 22,
        "missing_minute_clocks": [], "economic_log_returns": None,
        "forecast_total_variance": None, "pilot_input_acceptance": False,
        "authority": dict(AUTHORITY) | {"raw_source_scans": 3},
        "corporate_actions": {"selected_spy_records": [first]},
        "observations": rows,
    }
    folder = tmp_path / "data/research"
    stock_path = folder / "stock.json"
    stock_sha, stock_fp = seal(stock_path, stock)
    proof = {
        "contract": "atlas-options-native-spy-action-source-proof-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "date_window": ["2019-10-01", "2020-03-31"],
        "prior_stock_review_fingerprint": stock_fp,
        "prior_stock_review_sha256": stock_sha,
        "source_page_hashes_verified": True, "native_ledger_exactly_matches_original_pages": True,
        "original_prior_window_candidates_reconciled": 1,
        "historical_pit_publication_qualified": False,
        "action_effective_date_coverage_qualified": False,
        "economic_log_returns": None, "forecast_total_variance": None,
        "pilot_input_acceptance": False, "authority": dict(AUTHORITY) | {"raw_source_scans": 2},
        "source_scans": {"raw_option_histories": 0},
        "spy_action_candidates": [first, future],
    }
    proof_path = folder / "proof.json"
    proof_sha, proof_fp = seal(proof_path, proof)
    review_binding = subject.PinnedReview("data/research/stock.json", stock_sha, stock_fp)
    proof_binding = subject.PinnedProof("data/research/proof.json", proof_sha, proof_fp)
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda _: None,
    )
    return settings, review_binding, proof_binding, stock_path, proof_path, stock, proof


def test_two_pinned_reports_compute_20_conditionals_without_historical_authority(tmp_path):
    settings, stock_binding, proof_binding, *_ = invented(tmp_path)
    report = subject.build_spy_prior_variance_sensitivity(
        settings, stock_binding=stock_binding, proof_binding=proof_binding,
    )
    assert report["prior_close_count"] == 21 and report["return_count"] == 20
    assert report["decision_spot_raw"] == "321.60"
    ex = next(row for row in report["return_rows"] if row["end_session"] == "2019-12-20")
    assert ex["scenario_ex_date_cash_per_original_share"] == "1.569992"
    assert Decimal(ex["one_dividend_conditional_log_return"]) > Decimal(ex["raw_close_log_return"])
    assert all(x["historical_return_qualified"] is False for x in report["return_rows"])
    assert report["later_dividend_excluded"]["ex_date"] == "2020-03-20"
    assert report["economic_log_returns"] is report["forecast_total_variance"] is None
    assert report["pilot_input_acceptance"] is report["historical_performance_evidence"] is False
    assert not any(report["authority"].values())
    assert not any(report["source_scans"].values())
    assert report["conditional_variance"]["historical_feature_authority"] is False
    assert report["report_fingerprint"] == _fingerprint(
        {k: v for k, v in report.items() if k != "report_fingerprint"}
    )


@pytest.mark.parametrize("corruption", [
    "stock_bytes", "proof_bytes", "stock_resigned", "proof_resigned",
    "late_spot", "missing_close", "no_dividend", "extra_dividend",
    "future_dividend_before_cutoff", "ex_date_becomes_publication", "bad_price",
    "wrong_daily_delta", "wrong_authority", "invalid_dividend_rate",
])
def test_pinned_source_semantics_fail_closed(tmp_path, corruption):
    settings, stock_binding, proof_binding, stock_path, proof_path, stock, proof = invented(tmp_path)
    if corruption == "stock_bytes":
        stock_path.write_bytes(stock_path.read_bytes() + b"drift")
    elif corruption == "proof_bytes":
        proof_path.write_bytes(proof_path.read_bytes() + b"drift")
    else:
        if corruption in ("stock_resigned", "late_spot", "missing_close", "bad_price", "wrong_daily_delta", "wrong_authority"):
            if corruption == "stock_resigned":
                stock["pilot_input_acceptance"] = True
            if corruption == "late_spot":
                stock["observations"][-1]["interval_end_utc"] = (FEATURE_CUTOFF + timedelta(minutes=1)).isoformat()
            if corruption == "missing_close":
                stock["observations"].pop(0)
            if corruption == "bad_price":
                stock["observations"][0]["raw_close"] = "NaN"
            if corruption == "wrong_daily_delta":
                stock["observations"][0]["minute_minus_daily"] = "1.00"
            if corruption == "wrong_authority":
                stock["authority"]["live"] = True
            sha, fp = seal(stock_path, stock)
            stock_binding = subject.PinnedReview(stock_binding.path, sha, fp)
            # Rebind the fixture's genuine new stock identity without relaxing the proof checks.
            proof["prior_stock_review_fingerprint"] = fp
            proof["prior_stock_review_sha256"] = sha
            sha, fp = seal(proof_path, proof)
            proof_binding = subject.PinnedProof(proof_binding.path, sha, fp)
        else:
            if corruption == "proof_resigned":
                proof["historical_pit_publication_qualified"] = True
            elif corruption == "no_dividend":
                proof["spy_action_candidates"] = proof["spy_action_candidates"][1:]
            elif corruption == "extra_dividend":
                proof["spy_action_candidates"].append(proof["spy_action_candidates"][0])
            elif corruption == "future_dividend_before_cutoff":
                proof["spy_action_candidates"][1]["payload"]["process_date"] = "2019-12-01"
            elif corruption == "ex_date_becomes_publication":
                proof["spy_action_candidates"][0]["historical_available_at_utc"] = "2019-12-20T00:00:00+00:00"
            elif corruption == "invalid_dividend_rate":
                proof["spy_action_candidates"][0]["payload"]["rate"] = "-1"
                stock["corporate_actions"]["selected_spy_records"][0]["payload"]["rate"] = "-1"
            if corruption == "invalid_dividend_rate":
                stock_sha, stock_fp = seal(stock_path, stock)
                stock_binding = subject.PinnedReview(stock_binding.path, stock_sha, stock_fp)
                proof["prior_stock_review_sha256"] = stock_sha
                proof["prior_stock_review_fingerprint"] = stock_fp
            sha, fp = seal(proof_path, proof)
            proof_binding = subject.PinnedProof(proof_binding.path, sha, fp)
    with pytest.raises(subject.SpyPriorVarianceError):
        subject.build_spy_prior_variance_sensitivity(
            settings, stock_binding=stock_binding, proof_binding=proof_binding,
        )


def test_cli_writes_one_small_idempotent_packet_and_rejects_conflict(tmp_path, monkeypatch, capsys):
    settings, sb, pb, *_ = invented(tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "build_spy_prior_variance_sensitivity",
                        lambda *a, **k: subject.build_spy_prior_variance_sensitivity(
                            settings, stock_binding=sb, proof_binding=pb,
                        ))
    assert cli.main(["--save-report"]) == 0
    assert cli.main(["--save-report"]) == 0
    directory = tmp_path / "data/research/options_native_spy_prior_variance_sensitivity_v1"
    output = list(directory.glob("*.json"))
    assert len(output) == 1 and output[0].stat().st_size < 256 * 1024
    assert "UNQUALIFIED" in capsys.readouterr().out
    output[0].write_text("Original evidence must be retained", encoding="utf-8")
    assert cli.main(["--save-report"]) == 3
    assert output[0].read_text(encoding="utf-8") == "Original evidence must be retained"
