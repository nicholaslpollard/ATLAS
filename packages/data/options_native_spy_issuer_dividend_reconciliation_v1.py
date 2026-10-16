from __future__ import annotations

"""Original US issuer 33-event SPY cash comparison, strictly retrospective.

Three pinned accepted JSON reports and one pinned original XLSX only. Historical
announcement/revision clocks, complete corporate-action coverage and executable
features remain unqualified. This is NOT an options signal or performance trial.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_archival_action_timeline_v1 import PinnedSource, _load_pinned
from packages.data.options_native_spy_dividend_negative_control_v1 import ARCHIVE
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    KNOWN_ABSENCE, reference_schedule, reconcile_reference_to_archive,
)
from packages.data.options_native_spy_issuer_distributions_receipt_v1 import (
    ISSUER_URL, PREVIOUS_GRID, XLSX_MAX_BYTES, XML_NS, _cell_text,
    _safe_xlsx_bytes, _shared_strings,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-us-issuer-dividend-reconciliation-v1"
RECEIPT = PinnedSource(
    "data/research/options_native_spy_issuer_distributions_receipt_v1/c84814fcba520320.json",
    "e0274d0628a1f4ae90510ef09359bab7073394689edf7d6f744ae224ca2f0f57",
    "c84814fcba52032006d0f91890e7df1cdeef0c92774bc403a62ef968109e8ce4",
)
RAW_SHA = "6b65cbf956b5d25705d08470006a0e97e6a7d2a0d5cfd08b63f6f79783b06320"
RAW_BYTES = 581216
RAW_PATH = (
    "data/research/options_native_spy_issuer_distributions_receipt_v1/raw/"
    + RAW_SHA + ".xlsx"
)
EXPECTED_HEADERS = {
    "A": "FUND NAME", "B": "TICKER", "C": "CUSIP",
    "D": "EX-DATE", "E": "RECORD DATE", "F": "PAYABLE DATE",
    "G": "DIVIDEND ($)", "H": "SHORT TERM CAPITAL GAIN ($)",
    "I": "LONG TERM CAPITAL GAIN ($)", "J": "FREQUENCY",
}
IDENTITY_NAME = "State Street® SPDR® S&P 500® ETF Trust"
MIN_EX_DATE = "2017-12-15"
MAX_EX_DATE = "2025-12-19"
MAX_WORKBOOK_ROWS = 15000


class IssuerDividendReconciliationError(ValueError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise IssuerDividendReconciliationError(message)


def _date(s: object) -> str:
    _require(isinstance(s, str) and len(s) == 10, "issuer date missing or malformed")
    try:
        dt = datetime.strptime(s, "%m/%d/%Y")
    except ValueError as exc:
        raise IssuerDividendReconciliationError("issuer date invalid") from exc
    _require(dt.strftime("%m/%d/%Y") == s, "issuer date is not canonical MM/DD/YYYY")
    return dt.date().isoformat()


def _cash(s: object, *, require_positive: bool) -> Decimal:
    _require(isinstance(s, str) and 0 < len(s.strip()) <= 40, "issuer cash missing")
    try:
        amount = Decimal(s.strip())
    except InvalidOperation as exc:
        raise IssuerDividendReconciliationError("issuer cash not decimal") from exc
    _require(amount.is_finite() and Decimal(0) <= amount <= Decimal("1000")
             and amount.as_tuple().exponent >= -9,
             "issuer cash nonfinite or outside bounded precision")
    if require_positive:
        _require(amount > 0, "issuer dividend must be positive")
    return amount


def _extract_issuer_spy_rows(raw: bytes) -> tuple[list[dict[str, Any]], int]:
    """Parse all SPY rows from exact workbook format; preserve original row numbers."""
    _safe_xlsx_bytes(raw)
    from io import BytesIO
    try:
        z = ZipFile(BytesIO(raw), "r")
    except BadZipFile as exc:
        raise IssuerDividendReconciliationError("issuer XLSX ZIP malformed") from exc
    with z:
        _require("xl/worksheets/sheet1.xml" in z.namelist()
                 and "xl/sharedStrings.xml" in z.namelist(),
                 "pinned issuer worksheet/shared strings absent")
        shared = _shared_strings(z, set(z.namelist()))
        found: list[dict[str, Any]] = []
        seen_dates: set[str] = set()
        count = 0
        header_seen = False
        try:
            with z.open("xl/worksheets/sheet1.xml") as f:
                for _event, node in ET.iterparse(f, events=("end",)):
                    if node.tag != XML_NS + "row":
                        continue
                    count += 1
                    _require(count <= MAX_WORKBOOK_ROWS,
                             "issuer workbook row count beyond bounded expected population")
                    source_r = node.attrib.get("r")
                    _require(isinstance(source_r, str) and source_r.isdigit()
                             and int(source_r) == count,
                             "issuer original row numbering is not contiguous")
                    values: dict[str, str] = {}
                    for cell in node:
                        if cell.tag != XML_NS + "c":
                            continue
                        coord = cell.attrib.get("r", "")
                        col = coord.rstrip("0123456789")
                        _require(col in EXPECTED_HEADERS and coord == f"{col}{count}"
                                 and col not in values,
                                 "issuer workbook changed column layout or repeated cell")
                        values[col] = _cell_text(cell, shared).strip()
                    if count == 1:
                        _require(values == EXPECTED_HEADERS,
                                 "issuer workbook historical column headers changed")
                        header_seen = True
                    elif values.get("B") == "SPY" or values.get("C") == "78462F103":
                        _require(values.get("A") == IDENTITY_NAME
                                 and values.get("B") == "SPY"
                                 and values.get("C") == "78462F103"
                                 and values.get("J") == "Quarterly",
                                 "SPY identity/CUSIP/frequency disagreement")
                        ex = _date(values.get("D"))
                        record = _date(values.get("E"))
                        payment = _date(values.get("F"))
                        _require(ex not in seen_dates and ex <= record <= payment,
                                 "SPY duplicate ex-date or nonmonotonic lifecycle dates")
                        seen_dates.add(ex)
                        dividend = _cash(values.get("G"), require_positive=True)
                        for gain_col in ("H", "I"):
                            if values.get(gain_col, ""):
                                _cash(values[gain_col], require_positive=False)
                        found.append({
                            "source_row": count, "ex_date": ex,
                            "record_date": record, "payable_date": payment,
                            "cash_per_share_usd": str(dividend),
                            "short_term_capital_gain_raw": values.get("H") or None,
                            "long_term_capital_gain_raw": values.get("I") or None,
                        })
                    node.clear()
        except (ET.ParseError, BadZipFile, UnicodeError, ValueError) as exc:
            raise IssuerDividendReconciliationError("issuer XLSX cells malformed") from exc
    _require(header_seen and count == 13385 and len(found) == 136,
             "issuer worksheet source row population changed")
    return found, count


def _compare_source_rows(
    rows: list[dict[str, Any]], reference: dict[str, Decimal], archive: dict[str, Any]
) -> dict[str, Any]:
    in_period = [r for r in rows if MIN_EX_DATE <= r["ex_date"] <= MAX_EX_DATE]
    _require(len(in_period) == 33 and len({r["ex_date"] for r in in_period}) == 33,
             "issuer expected 2017-2025 distribution population differs")
    by_date = {row["ex_date"]: row for row in in_period}
    _require(set(by_date) == set(reference), "issuer/independent historical ex-date disagreement")
    archive_comparison = reconcile_reference_to_archive(archive, reference)
    native = {row["payload"]["ex_date"]: Decimal(str(row["payload"]["rate"]))
              for row in archive["action_candidates"]}
    _require(set(reference) - set(native) == {KNOWN_ABSENCE},
             "previous 32-event archive omission moved")

    issuer_vs_reference: list[dict[str, str]] = []
    issuer_vs_archive: list[dict[str, str]] = []
    for when in sorted(reference):
        row = by_date[when]
        issuer_amt = Decimal(row["cash_per_share_usd"])
        reference_amt = reference[when]
        if issuer_amt != reference_amt:
            issuer_vs_reference.append({
                "ex_date": when, "issuer_cash": str(issuer_amt),
                "retrospective_reference_cash": str(reference_amt),
                "issuer_minus_reference": str(issuer_amt - reference_amt)})
        if when in native and issuer_amt != native[when]:
            issuer_vs_archive.append({
                "ex_date": when, "issuer_cash": str(issuer_amt),
                "original_archive_cash": str(native[when]),
                "issuer_minus_archive": str(issuer_amt - native[when])})
    _require(issuer_vs_reference == [{
                "ex_date": "2018-03-16", "issuer_cash": "1.096775",
                "retrospective_reference_cash": "1.09678",
                "issuer_minus_reference": "-0.000005",
             }], "unexplained issuer versus reference cash discrepancy")
    _require(issuer_vs_archive == [{
                "ex_date": "2020-06-19", "issuer_cash": "1.366242",
                "original_archive_cash": "1.3662419",
                "issuer_minus_archive": "1E-7",
             }], "unexplained issuer versus archive cash discrepancy")
    _require(by_date[KNOWN_ABSENCE]["cash_per_share_usd"] == "1.245568"
             and by_date[KNOWN_ABSENCE]["source_row"] == 9163,
             "issuer omitted June 2018 source witness changed")
    _require(archive_comparison["archived_event_count"] == 32
             and archive_comparison["known_missing_ex_dates"] == [KNOWN_ABSENCE],
             "legacy archive baseline diverged")
    return {
        "issuer_period_events": [by_date[d] for d in sorted(by_date)],
        "issuer_vs_reference_differences": issuer_vs_reference,
        "issuer_vs_archive_differences": issuer_vs_archive,
        "missing_from_original_action_archive": [KNOWN_ABSENCE],
        "archived_cash_events_matched_by_ex_date": 32,
        "issuer_event_count": 33,
        "issuer_historical_snapshot_matches_expected_ex_dates": True,
    }


def build_issuer_spy_reconciliation(settings: AtlasSettings) -> dict[str, Any]:
    receipt = _load_pinned(settings, RECEIPT)
    grid = _load_pinned(settings, PREVIOUS_GRID)
    archive = _load_pinned(settings, ARCHIVE)
    _require(receipt.get("contract") == "atlas-options-native-spy-us-issuer-xlsx-receipt-v1"
             and receipt.get("status") == "US_ISSUER_WORKBOOK_CAPTURED_LAYOUT_ONLY_NO_PIT"
             and receipt.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and receipt.get("original_xlsx_sha256") == RAW_SHA
             and receipt.get("original_xlsx_bytes") == RAW_BYTES
             and receipt.get("source_url") == ISSUER_URL
             and receipt.get("source_requests", {}).get("issuer_document_gets") == 1
             and receipt.get("spy_identity_matching_rows") == 136
             and receipt.get("worksheet_scan_summary") == [{
                 "sheet_member": "xl/worksheets/sheet1.xml",
                 "rows_inspected": 13385, "spy_identity_matching_rows": 136,
             }]
             and receipt.get("pilot_input_acceptance") is False
             and receipt.get("authority") == dict(AUTHORITY),
             "pinned issuer receipt's original source or authority changed")
    _require(grid.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and grid.get("status") == "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES"
             and grid.get("physically_price_complete_decisions") == 407
             and grid.get("retrospective_dividend_touched_decisions") == 149
             and grid.get("pilot_input_acceptance") is False
             and grid.get("authority") == dict(AUTHORITY)
             and archive.get("status") == "ARCHIVAL_SPY_ACTION_INDEX_ONLY_PIT_AND_COVERAGE_UNQUALIFIED"
             and archive.get("action_candidates_by_type") == {"cash_dividends": 32}
             and archive.get("authority") == dict(AUTHORITY),
             "upstream research scope or authority changed")

    path = settings.resolved_path(RAW_PATH)
    _require(path.is_file() and not path.is_symlink()
             and path.stat().st_size == RAW_BYTES and RAW_BYTES <= XLSX_MAX_BYTES,
             "original issuer XLSX missing/changed")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == RAW_SHA,
             "immutable issuer XLSX byte identity mismatch")
    expected = reference_schedule()
    _require(grid.get("retrospective_reference", {}).get("rows") ==
             [{"us_ex_date": d, "us_cash_per_share": str(v)} for d, v in expected.items()],
             "previous 33-row retrospective reference changed")
    rows, total = _extract_issuer_spy_rows(raw)
    outcome = _compare_source_rows(rows, expected, archive)
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "FULL_33_SPY_ISSUER_CASH_EVENTS_RECONCILED_RETROSPECTIVE_NO_PIT",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "pinned_source_reports": {
            "issuer_receipt": {"fingerprint": RECEIPT.fingerprint, "raw_sha256": RECEIPT.sha256},
            "retrospective_grid": {"fingerprint": PREVIOUS_GRID.fingerprint, "raw_sha256": PREVIOUS_GRID.sha256},
            "original_action_archive": {"fingerprint": ARCHIVE.fingerprint, "raw_sha256": ARCHIVE.sha256},
        },
        "issuer_source_url": ISSUER_URL,
        "issuer_original_sha256": RAW_SHA,
        "issuer_original_bytes": RAW_BYTES,
        "issuer_workbook_rows": total,
        "issuer_all_time_spy_rows": len(rows),
        "issuer_table_date_range": [MIN_EX_DATE, MAX_EX_DATE],
        "original_source_capture_clock": receipt["retrieved_at_utc"],
        **outcome,
        "issuer_publication_clock_in_2018_2025_proved": False,
        "issuer_asof_amendment_or_revision_history_proved": False,
        "other_corporate_action_coverage_qualified": False,
        "historical_economic_log_returns": None,
        "forecast_total_variance": None,
        "option_implied_variance": None,
        "historical_option_fills": None,
        "historical_backtest_authorized": False,
        "pilot_input_acceptance": False,
        "source_requests": {"issuer_gets": 0, "provider_gets": 0, "broker_gets": 0,
                            "stock_price_scans": 0, "action_ledger_scans": 0,
                            "option_scans": 0, "outcome_scans": 0,
                            "pinned_json_reports": 3, "original_xlsx_reads": 1},
        "authority": dict(AUTHORITY),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
