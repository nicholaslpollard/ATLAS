from __future__ import annotations

import json
from copy import deepcopy

import pytest

import scripts.audit_thetadata_free_eod_receipt_v1 as audit


def _row(**overrides):
    row = {
        "created": "2026-10-16T17:15:47.891000-04:00",
        "last_trade": "2026-10-16T16:13:55.792000-04:00",
        "open": 12.9, "high": 12.9, "low": 8.24, "close": 8.37,
        "volume": 3870, "count": 778,
        "bid_size": 174, "bid_exchange": 65, "bid": 8.33,
        "bid_condition": 50, "ask_size": 84, "ask_exchange": 42,
        "ask": 8.44, "ask_condition": 50,
    }
    row.update(overrides)
    return row


def _receipt():
    stock = _row(
        created="2026-10-16T17:15:45.169000-04:00",
        last_trade="2026-10-16T17:15:40.180000-04:00",
        open=773.2, high=773.25, low=760.64, close=763.25,
        volume=63916385, count=732258,
        bid_size=80, bid=763.32, ask=763.39, ask_size=40,
        bid_condition=0, ask_condition=0,
    )
    opt = _row(
        symbol="SPY", expiration="2026-11-20",
        right="CALL", strike=775.0,
    )
    responses = [
        {
            "method": "stock_history_eod", "status": "RECEIVED",
            "query": {"symbol": "SPY", "start_date": "2026-10-16",
                      "end_date": "2026-10-16"},
            "rows": 1, "columns": list(audit.PROVIDER_COLUMNS),
            "dtypes": {k: "object" for k in audit.PROVIDER_COLUMNS},
            "normalized_rows": [stock], "sample_rows": [stock],
        },
        {
            "method": "option_history_eod", "status": "RECEIVED",
            "query": {"symbol": "SPY", "start_date": "2026-10-16",
                      "end_date": "2026-10-16", "expiration": "2026-11-20",
                      "strike": "*", "right": "call", "strike_range": 2},
            "rows": 1, "columns": list(audit.OPTION_COLUMNS),
            "dtypes": {k: "object" for k in audit.OPTION_COLUMNS},
            "normalized_rows": [opt], "sample_rows": [opt],
        },
    ]
    body = {
        "contract": audit.CONTRACT,
        "status": "TWO_EOD_DATAFRAMES_RECEIVED",
        "request_attempts": 2, "request_cap": 2,
        "thetadata_version": "1.0.12",
        "responses": responses,
    }
    return {**body, "fingerprint": audit._sha(body)}


def _resign(receipt):
    result = deepcopy(receipt)
    result["fingerprint"] = audit._sha(
        {k: v for k, v in result.items() if k != "fingerprint"}
    )
    return result


def test_audit_actual_eod_schema_timing_and_price_diagnostics(tmp_path):
    source = _receipt()
    summary = audit.audit_receipt(source)
    assert summary["provider_requests_by_audit"] == 0
    assert summary["status"] == "EOD_SHAPE_AUDITED_NOT_INTRADAY_EVIDENCE"
    assert summary["retained_source_fingerprint"] == source["fingerprint"]
    assert summary["response_audits"][0]["rows"] == 1
    assert summary["response_audits"][0]["created_after_16_et_rows"] == 1
    assert summary["response_audits"][1]["last_trade_after_16_et_rows"] == 1
    opt = summary["response_audits"][1]["contract_diagnostics"][0]
    assert opt["right"] == "call"
    assert opt["strike"] == 775.0
    assert opt["spread_to_mid"] == pytest.approx(.11 / 8.385)
    assert opt["bid_size"] == 174 and opt["ask_size"] == 84
    path = audit.persist_audit(summary, tmp_path)
    assert path == audit.persist_audit(summary, tmp_path)
    assert json.loads(path.read_text())["fingerprint"] == audit._sha(summary)


def test_modified_source_fingerprint_rejected_before_interpretation():
    source = _receipt()
    source["responses"][1]["normalized_rows"][0]["ask"] = 900000
    with pytest.raises(audit.RetainedReceiptError, match="FINGERPRINT_MISMATCH"):
        audit.audit_receipt(source)


@pytest.mark.parametrize("target,mutate,reason", [
    ("status", lambda d: d.update(status="SOURCE_SHAPE_INCOMPLETE"),
     "NOT_TWO_SUCCESSFUL"),
    ("request_attempts", lambda d: d.update(request_attempts=3),
     "WRONG_REQUEST_BUDGET"),
    ("option_scope",
     lambda d: d["responses"][1]["query"].update(expiration="2026-12-18"),
     "OPTION_SCOPE_MISMATCH"),
    ("option_identity",
     lambda d: d["responses"][1]["normalized_rows"][0].update(right="PUT"),
     "WRONG_OPTION_CONTRACT"),
    ("future_date",
     lambda d: d["responses"][1]["normalized_rows"][0].update(
         created="2026-10-17T17:15:47.891000-04:00"),
     "EOD_REPORT_DATE_MISMATCH"),
    ("crossed_quote",
     lambda d: d["responses"][1]["normalized_rows"][0].update(
         bid=11.0, ask=9.0),
     "EOD_CROSSED_QUOTE"),
    ("wrong_timezone_offset",
     lambda d: d["responses"][1]["normalized_rows"][0].update(
         last_trade="2026-10-16T16:13:55.792000+00:00"),
     "UNEXPECTED_ET_OFFSET_LAST_TRADE"),
    ("missing_field",
     lambda d: d["responses"][1]["normalized_rows"][0].pop("bid_size"),
     "EOD_ROW_COLUMNS_MISMATCH"),
])
def test_source_integrity_and_schema_fail_closed(target, mutate, reason):
    source = _receipt()
    mutate(source)
    source = _resign(source)
    with pytest.raises(audit.RetainedReceiptError, match=reason):
        audit.audit_receipt(source)


def test_exactly_one_local_receipt_and_never_fallback_to_provider(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(audit, "RECEIPT_DIR", tmp_path)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.main([]) == 3
    assert "provider requests" in capsys.readouterr().out.lower()
    source = _receipt()
    file = tmp_path / (audit.PREFIX + source["fingerprint"][:16] + ".json")
    file.write_text(json.dumps(source), encoding="utf-8")
    assert audit.main([]) == 0
    output = capsys.readouterr().out
    assert "provider_requests=0" in output
    assert "CALL strike=775" in output
    assert len(list(tmp_path.glob("thetadata_free_eod_retained_audit_v1_*.json"))) == 1
    file2 = tmp_path / (audit.PREFIX + "another.json")
    file2.write_text("{}", encoding="utf-8")
    assert audit.main([]) == 3
    assert "EXPECTED_ONE_RETAINED_RECEIPT_FOUND_2" in capsys.readouterr().out
