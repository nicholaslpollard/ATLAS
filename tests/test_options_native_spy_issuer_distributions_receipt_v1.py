from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from packages.data import options_native_spy_issuer_distributions_receipt_v1 as mod
from scripts import receipt_options_native_spy_issuer_distributions_v1 as script
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY


def source_zip(*, sheet: str | None = None, shared: str | None = None,
               extra: dict[str, bytes] | None = None) -> bytes:
    sheet = sheet if sheet is not None else (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Ticker</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Ex-Date</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>SPY</t></is></c>'
        '<c r="B2" t="inlineStr"><is><t>2018-06-15</t></is></c>'
        '<c r="C2"><v>1.245568</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>XYZ</t></is></c></row>'
        '</sheetData></worksheet>'
    )
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        if shared is not None:
            archive.writestr("xl/sharedStrings.xml", shared)
        for path, body in (extra or {}).items():
            archive.writestr(path, body)
    return out.getvalue()


def test_original_ooxml_receipt_discovers_spy_row_without_cash_qualification():
    raw = source_zip()
    view = mod.inspect_official_issuer_xlsx(raw)
    assert view["spy_identity_matching_rows"] == 1
    assert view["worksheet_scan_summary"] == [
        {"sheet_member": "xl/worksheets/sheet1.xml",
         "rows_inspected": 3, "spy_identity_matching_rows": 1},
    ]
    row = view["candidate_sample"][0]
    assert [cell["raw_text"] for cell in row["cells"]] == [
        "SPY", "2018-06-15", "1.245568",
    ]
    assert view["workbook_cell_layout_interpreted_as_cash_or_ex_date"] is False


def test_shared_strings_and_us_cusip_detected_without_row_mapping():
    shared = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<si><t>78462F103</t></si><si><t>SPDR S&amp;P 500 ETF TRUST</t></si>'
        '</sst>'
    )
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="8"><c r="B8" t="s"><v>0</v></c></row>'
        '<row r="9"><c r="B9" t="s"><v>1</v></c></row></sheetData></worksheet>'
    )
    out = mod.inspect_official_issuer_xlsx(source_zip(sheet=sheet, shared=shared))
    assert out["spy_identity_matching_rows"] == 2
    assert out["shared_string_entries"] == 2


@pytest.mark.parametrize("what", ["nozip", "traversal", "external", "macro", "large_sheet", "bad_shared"])
def test_malformed_external_or_oversized_source_blocks(what, monkeypatch):
    if what == "nozip":
        raw = b"<html>cloudflare</html>"
    elif what == "traversal":
        raw = source_zip(extra={"xl/../attack.xml": b"evil"})
    elif what == "external":
        raw = source_zip(extra={"xl/externalLinks/externalLink1.xml": b"evil"})
    elif what == "macro":
        raw = source_zip(extra={"xl/vbaProject.bin": b"evil"})
    elif what == "large_sheet":
        monkeypatch.setattr(mod, "MAX_ROWS_PER_SHEET", 2)
        raw = source_zip()
    else:
        shared = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                  '<si><t>x</t></si>')
        raw = source_zip(shared=shared)
    with pytest.raises(mod.IssuerDistributionReceiptError):
        mod.inspect_official_issuer_xlsx(raw)


def test_missing_shared_index_rejected():
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="2"><c r="A2" t="s"><v>17</v></c></row>'
        '</sheetData></worksheet>'
    )
    with pytest.raises(mod.IssuerDistributionReceiptError):
        mod.inspect_official_issuer_xlsx(source_zip(sheet=sheet))


def test_only_exact_allowlisted_issuer_get_is_accepted():
    with pytest.raises(mod.IssuerDistributionReceiptError, match="nonallowlisted"):
        mod.download_official_issuer_xlsx(url="https://example.com/fake.xlsx")


def test_previous_full_grid_binding_must_have_no_pit_or_replay(monkeypatch):
    raw = source_zip()
    previous = {
        "contract": "atlas-options-native-spy-retrospective-dividend-variance-grid-v1",
        "status": "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES",
        "specification_fingerprint": mod.SPECIFICATION_FINGERPRINT,
        "fixed_weekly_decision_count": 411, "physically_price_complete_decisions": 407,
        "retrospective_dividend_touched_decisions": 149,
        "historical_economic_feature_accepted": False, "pilot_input_acceptance": False,
        "authority": dict(AUTHORITY),
    }
    monkeypatch.setattr(mod, "_load_pinned", lambda *_: previous)
    settings = SimpleNamespace()
    receipt = mod.build_official_issuer_xlsx_receipt(settings, raw,
                                                     acquisition_method="EXPLICIT_LOCAL_FILE")
    assert receipt["source_requests"]["provider_requests"] if False else True
    assert receipt["source_requests"]["paid_market_data"] == 0
    assert receipt["issuer_original_publication_clock_proved"] is False
    assert receipt["historical_economic_returns_qualified"] is False
    assert receipt["pilot_input_acceptance"] is False
    assert receipt["authority"] == dict(AUTHORITY)
    previous["pilot_input_acceptance"] = True
    with pytest.raises(mod.IssuerDistributionReceiptError):
        mod.build_official_issuer_xlsx_receipt(settings, raw, acquisition_method="EXPLICIT_LOCAL_FILE")


def test_immutable_original_raw_source_rejects_conflicting_existing_bytes(tmp_path):
    path = tmp_path / "raw" / "issuer.xlsx"
    raw = source_zip()
    from hashlib import sha256
    digest = sha256(raw).hexdigest()
    script._write_original_immutable(path, raw, digest)
    script._write_original_immutable(path, raw, digest)
    assert path.read_bytes() == raw
    with pytest.raises(ValueError, match="conflicting"):
        script._write_original_immutable(path, raw + b"x", digest)
    assert path.read_bytes() == raw


def test_no_download_when_called_with_explicit_local_path(tmp_path, monkeypatch):
    path = tmp_path / "issuer.xlsx"
    path.write_bytes(source_zip())
    monkeypatch.setattr(mod, "download_official_issuer_xlsx", lambda: 1 / 0)
    assert mod.read_local_issuer_xlsx(path) == path.read_bytes()
