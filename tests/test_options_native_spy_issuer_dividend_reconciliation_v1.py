from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from packages.data import options_native_spy_issuer_dividend_reconciliation_v1 as mod
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    reference_schedule,
)


def issuer_fixture() -> list[dict]:
    schedule = reference_schedule()
    rows = []
    for index, (ex, value) in enumerate(reversed(list(schedule.items()))):
        rows.append({
            "source_row": 9133 + index, "ex_date": ex,
            "record_date": ex, "payable_date": ex,
            "cash_per_share_usd": "1.096775" if ex == "2018-03-16" else str(value),
            "short_term_capital_gain_raw": None,
            "long_term_capital_gain_raw": None,
        })
    assert next(x["source_row"] for x in rows if x["ex_date"] == "2018-06-15") == 9163
    return rows


def archive_fixture() -> dict:
    schedule = reference_schedule()
    candidates = []
    for ex, val in schedule.items():
        if ex == "2018-06-15":
            continue
        archived = ("1.096775" if ex == "2018-03-16" else
                    "1.3662419" if ex == "2020-06-19" else str(val))
        candidates.append({
            "action_type": "cash_dividends", "historical_available_at_utc": None,
            "point_in_time_qualified": False,
            "payload": {"symbol": "SPY", "ex_date": ex, "rate": archived},
        })
    return {"action_candidates": candidates,
            "action_candidates_by_type": {"cash_dividends": 32},
            "archival_candidates_with_unknown_effective_date": 0}


def test_issuer_33_cash_exdates_and_original_32_events_reconcile():
    out = mod._compare_source_rows(issuer_fixture(), reference_schedule(), archive_fixture())
    assert out["issuer_event_count"] == 33
    assert out["archived_cash_events_matched_by_ex_date"] == 32
    assert out["missing_from_original_action_archive"] == ["2018-06-15"]
    assert out["issuer_vs_reference_differences"] == [{
        "ex_date": "2018-03-16", "issuer_cash": "1.096775",
        "retrospective_reference_cash": "1.09678",
        "issuer_minus_reference": "-0.000005",
    }]
    assert out["issuer_vs_archive_differences"] == [{
        "ex_date": "2020-06-19", "issuer_cash": "1.366242",
        "original_archive_cash": "1.3662419", "issuer_minus_archive": "1E-7",
    }]


@pytest.mark.parametrize("change", ["missing_ex", "extra_ex", "changed_cash", "changed_archive",
                                    "missing_archival", "nonzero_capital_gain", "wrong_omission_source_row"])
def test_any_new_unexplained_dividend_drift_abstains(change):
    rows, archive = issuer_fixture(), archive_fixture()
    if change == "missing_ex":
        rows.pop()
    elif change == "extra_ex":
        rows.append({**rows[0], "ex_date": "2018-05-11"})
    elif change == "changed_cash":
        rows[0]["cash_per_share_usd"] = "3.0"
    elif change == "changed_archive":
        archive["action_candidates"][0]["payload"]["rate"] = "0.10"
    elif change == "missing_archival":
        archive["action_candidates"].pop()
    elif change == "nonzero_capital_gain":
        rows[0]["long_term_capital_gain_raw"] = "0.01"
    elif change == "wrong_omission_source_row":
        next(r for r in rows if r["ex_date"] == "2018-06-15")["source_row"] = 5
    with pytest.raises((ValueError, KeyError)):
        mod._compare_source_rows(rows, reference_schedule(), archive)


@pytest.mark.parametrize("value", ["", "2018-06-15", "06/15/18", "13/01/2018", "06/00/2018",
                                    "02/30/2018", None, "6/15/2018"])
def test_ex_date_must_be_explicit_month_day_year(value):
    with pytest.raises(ValueError):
        mod._date(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "1001", "", None,
                                    "0.1234567890", "not-a-number"])
def test_cash_distribution_positive_and_bounded(value):
    with pytest.raises(ValueError):
        mod._cash(value, require_positive=True)


def synthetic_workbook(*, mutate_header=False, duplicate_ex=False, corrupted_cash=False,
                       count_rows=13385) -> bytes:
    """Synthetic cells use the exact physical 136-SPY/13,385-row layout, no real history."""
    tags = []
    headers = mod.EXPECTED_HEADERS.copy()
    if mutate_header:
        headers["D"] = "UNKNOWN DATE"
    def cell(col, idx, text):
        return (f'<c r="{col}{idx}" t="inlineStr"><is><t>'
                + escape(str(text)) + '</t></is></c>')
    tags.append('<row r="1">' + ''.join(cell(k, 1, v) for k, v in headers.items()) + '</row>')
    for idx in range(2, count_rows + 1):
        if 9130 <= idx <= 9265:
            when = date(1990, 1, 1) + timedelta(days=idx)
            if idx == 9163:
                when = date(2018, 6, 15)
            if idx == 9164 and duplicate_ex:
                when = date(2018, 6, 15)
            iso = when.strftime("%m/%d/%Y")
            fields = {
                "A": mod.IDENTITY_NAME, "B": "SPY", "C": "78462F103",
                "D": iso, "E": iso, "F": iso, "J": "Quarterly",
            }
            pieces = [cell(col, idx, val) for col, val in fields.items()]
            amt = "not-a-number" if (idx == 9163 and corrupted_cash) else "1.245568"
            pieces.append(cell("G", idx, amt))
            tags.append(f'<row r="{idx}">' + ''.join(pieces) + '</row>')
        else:
            tags.append(f'<row r="{idx}"/>')
    xml = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<sheetData>' + ''.join(tags) + '</sheetData></worksheet>')
    buff = BytesIO()
    with ZipFile(buff, "w", ZIP_DEFLATED) as zipf:
        zipf.writestr("xl/worksheets/sheet1.xml", xml)
        zipf.writestr("xl/sharedStrings.xml",
                      '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
    return buff.getvalue()


def test_full_original_layout_parser_retains_cited_row_and_detects_cash():
    rows, n = mod._extract_issuer_spy_rows(synthetic_workbook())
    assert n == 13385
    assert len(rows) == 136
    assert next(r for r in rows if r["ex_date"] == "2018-06-15") == {
        "source_row": 9163, "ex_date": "2018-06-15",
        "record_date": "2018-06-15", "payable_date": "2018-06-15",
        "cash_per_share_usd": "1.245568",
        "short_term_capital_gain_raw": None, "long_term_capital_gain_raw": None,
    }


@pytest.mark.parametrize("reason", ["wrong_header", "duplicate_ex", "wrong_cash", "wrong_total"])
def test_source_layout_or_value_drift_blocks(reason):
    kwargs = {
        "wrong_header": {"mutate_header": True},
        "duplicate_ex": {"duplicate_ex": True},
        "wrong_cash": {"corrupted_cash": True},
        "wrong_total": {"count_rows": 13384},
    }
    with pytest.raises(ValueError):
        mod._extract_issuer_spy_rows(synthetic_workbook(**kwargs[reason]))
