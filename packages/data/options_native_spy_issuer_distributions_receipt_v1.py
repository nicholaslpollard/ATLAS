from __future__ import annotations

"""Bounded original US issuer SPDR distribution XLSX receipt + row discovery.

No historical PIT qualification. Workbook cells are displayed as UNTRUSTED raw
source text; no auto-mapped cash amount/ex-date, predictor, or backtest.
"""

from datetime import UTC, datetime
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_archival_action_timeline_v1 import PinnedSource, _load_pinned
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-us-issuer-xlsx-receipt-v1"
ISSUER_URL = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "spdr-etf-historical-distributions.xlsx"
)
PREVIOUS_GRID = PinnedSource(
    "data/research/options_native_spy_full_period_retrospective_dividend_variance_v1/70bf12bdade00048.json",
    "1a67653fdd9cf57cdc585312bc03530cec6ff912808e2c4ca7f4a96df0cd3572",
    "70bf12bdade00048f4e1188cb7dfda5f55680911d355e9d4b1726baa47dd2ef1",
)
XLSX_MAX_BYTES = 32 * 1024 * 1024
ZIP_MAX_TOTAL_UNCOMPRESSED = 160 * 1024 * 1024
ZIP_MAX_ENTRY_BYTES = 80 * 1024 * 1024
ZIP_MAX_ENTRIES = 600
MAX_SHARED_STRINGS = 600000
MAX_SHARED_STRING_TOTAL_CHARACTERS = 24 * 1024 * 1024
MAX_ROWS_PER_SHEET = 750000
MAX_SHEETS = 70
MAX_SAMPLE_ROWS = 60
MAX_CELL_CAPTURE = 30
MAX_SAMPLE_CHARACTERS_PER_CELL = 180
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SPY_LABEL = re.compile(r"\bSPDR\s+(?:S&P\s*500|S\s*&\s*P\s*500)\b", re.IGNORECASE)
SPY_IDENTITY = {"SPY", "78462F103"}


class IssuerDistributionReceiptError(ValueError):
    pass


def _require(ok: bool, why: str) -> None:
    if not ok:
        raise IssuerDistributionReceiptError(why)


def _safe_xlsx_bytes(raw: bytes) -> None:
    _require(isinstance(raw, bytes) and 0 < len(raw) <= XLSX_MAX_BYTES,
             "issuer workbook empty or too large")
    _require(raw.startswith(b"PK\x03\x04"), "issuer receipt is not OOXML ZIP")


def download_official_issuer_xlsx(*, url: str = ISSUER_URL) -> bytes:
    """Only explicit operator download; one issuer HTTPS GET, no fallback."""
    _require(url == ISSUER_URL, "nonallowlisted workbook acquisition URL")
    req = Request(url, headers={
        "User-Agent": "ATLAS-Research-Source-Receipt/1.0",
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    })
    try:
        with urlopen(req, timeout=45) as response:
            final = response.geturl()
            parts = urlparse(final)
            _require(parts.scheme == "https" and parts.netloc == "www.ssga.com"
                     and final == ISSUER_URL, "issuer download redirected off pinned URL")
            if response.status != 200:
                raise IssuerDistributionReceiptError("issuer download returned non-200 status")
            raw = response.read(XLSX_MAX_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise IssuerDistributionReceiptError("one official issuer HTTPS download failed; no retry") from exc
    _safe_xlsx_bytes(raw)
    return raw


def read_local_issuer_xlsx(path: Path) -> bytes:
    path = Path(path)
    _require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= XLSX_MAX_BYTES,
             "explicit local issuer workbook absent, linked or oversized")
    raw = path.read_bytes()
    _safe_xlsx_bytes(raw)
    return raw


def _text_of_si(node: ET.Element) -> str:
    return "".join(e.text or "" for e in node.iter()
                   if e.tag == XML_NS + "t")


def _shared_strings(z: ZipFile, names: set[str]) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []
    info = z.getinfo("xl/sharedStrings.xml")
    _require(info.file_size <= ZIP_MAX_ENTRY_BYTES, "shared-string XML too large")
    strings: list[str] = []
    total = 0
    try:
        with z.open(info) as f:
            for _event, node in ET.iterparse(f, events=("end",)):
                if node.tag != XML_NS + "si":
                    continue
                value = _text_of_si(node)
                total += len(value)
                _require(len(strings) < MAX_SHARED_STRINGS
                         and total <= MAX_SHARED_STRING_TOTAL_CHARACTERS,
                         "issuer shared string population exceeds bounds")
                strings.append(value)
                node.clear()
    except (ET.ParseError, BadZipFile, UnicodeError, ValueError) as exc:
        raise IssuerDistributionReceiptError("shared-string XML invalid") from exc
    return strings


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    t = cell.attrib.get("t", "")
    if t == "inlineStr":
        return _text_of_si(cell)
    values = [e.text or "" for e in cell if e.tag == XML_NS + "v"]
    if t == "s":
        _require(len(values) == 1 and values[0].isdigit(),
                 "malformed shared-string reference")
        i = int(values[0])
        _require(0 <= i < len(shared), "shared-string index out of bounds")
        return shared[i]
    if t in ("str", "d", "n", "", "b", "e"):
        return values[0] if values else ""
    return ""


def _matches_spy(values: list[str]) -> bool:
    for raw in values:
        value = raw.strip().upper().replace("\u00a0", " ")
        if value in SPY_IDENTITY or SPY_LABEL.search(value):
            return True
    return False


def inspect_official_issuer_xlsx(raw: bytes) -> dict[str, Any]:
    """Inventory every worksheet with one bounded SPY candidate sample."""
    _safe_xlsx_bytes(raw)
    try:
        z = ZipFile(BytesIO(raw), "r")
    except BadZipFile as exc:
        raise IssuerDistributionReceiptError("invalid source XLSX ZIP") from exc
    with z:
        entries = z.infolist()
        _require(len(entries) <= ZIP_MAX_ENTRIES, "issuer archive has excessive members")
        paths: set[str] = set()
        uncompressed = 0
        for item in entries:
            name = item.filename.replace("\\", "/")
            _require(name not in paths and not name.startswith("/")
                     and ".." not in name.split("/")
                     and not name.startswith("xl/externalLinks/")
                     and not name.endswith("vbaProject.bin"),
                     "unsafe, duplicated, external-linked or macro-enabled issuer workbook")
            if item.is_dir():
                continue
            paths.add(name)
            uncompressed += item.file_size
            _require(item.file_size <= ZIP_MAX_ENTRY_BYTES
                     and uncompressed <= ZIP_MAX_TOTAL_UNCOMPRESSED,
                     "excessive OOXML uncompressed size")
            if item.compress_size:
                _require(item.file_size <= max(10000, item.compress_size * 600),
                         "unsafe OOXML expansion ratio")
        _require("[Content_Types].xml" in paths
                 and "xl/workbook.xml" in paths,
                 "missing OOXML workbook metadata")
        sheets = sorted(p for p in paths
                        if re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml", p))
        _require(0 < len(sheets) <= MAX_SHEETS, "no bounded worksheets in issuer workbook")
        strings = _shared_strings(z, paths)
        findings: list[dict[str, Any]] = []
        stats: list[dict[str, Any]] = []
        matched = 0
        for path in sheets:
            sheet_rows = 0
            sheet_matches = 0
            try:
                with z.open(path) as f:
                    for event, node in ET.iterparse(f, events=("end",)):
                        if node.tag != XML_NS + "row":
                            continue
                        sheet_rows += 1
                        _require(sheet_rows <= MAX_ROWS_PER_SHEET,
                                 "sheet row population exceeds bound")
                        vals: list[tuple[str, str]] = []
                        for cell in node:
                            if cell.tag != XML_NS + "c":
                                continue
                            ref = cell.attrib.get("r", "")
                            _require(len(ref) <= 12, "invalid cell coordinate")
                            val = _cell_text(cell, strings)
                            if val:
                                vals.append((ref, val))
                        if _matches_spy([v for _, v in vals]):
                            matched += 1
                            sheet_matches += 1
                            if len(findings) < MAX_SAMPLE_ROWS:
                                findings.append({
                                    "sheet_member": path,
                                    "row_ordinal": sheet_rows,
                                    "source_row_index": node.attrib.get("r"),
                                    "cells": [
                                        {"ref": ref, "raw_text": val[:MAX_SAMPLE_CHARACTERS_PER_CELL]}
                                        for ref, val in vals[:MAX_CELL_CAPTURE]
                                    ],
                                    "entire_row_values_preserved": len(vals) <= MAX_CELL_CAPTURE and
                                                                    all(len(v) <= MAX_SAMPLE_CHARACTERS_PER_CELL
                                                                        for _, v in vals),
                                })
                        node.clear()
            except (ET.ParseError, BadZipFile, UnicodeError, ValueError) as exc:
                raise IssuerDistributionReceiptError("issuer worksheet XML malformed") from exc
            stats.append({"sheet_member": path, "rows_inspected": sheet_rows,
                          "spy_identity_matching_rows": sheet_matches})
        return {"worksheet_scan_summary": stats,
                "shared_string_entries": len(strings),
                "spy_identity_matching_rows": matched,
                "candidate_rows_captured": len(findings),
                "candidate_sample": findings,
                "workbook_cell_layout_interpreted_as_cash_or_ex_date": False}


def build_official_issuer_xlsx_receipt(settings: AtlasSettings, raw: bytes, *,
                                       acquisition_method: str) -> dict[str, Any]:
    _require(acquisition_method in {"EXPLICIT_ONE_GET", "EXPLICIT_LOCAL_FILE"},
             "source intake mode unknown")
    previous = _load_pinned(settings, PREVIOUS_GRID)
    _require(previous.get("contract") ==
             "atlas-options-native-spy-retrospective-dividend-variance-grid-v1"
             and previous.get("status") ==
             "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES"
             and previous.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and previous.get("fixed_weekly_decision_count") == 411
             and previous.get("physically_price_complete_decisions") == 407
             and previous.get("retrospective_dividend_touched_decisions") == 149
             and previous.get("historical_economic_feature_accepted") is False
             and previous.get("pilot_input_acceptance") is False
             and previous.get("authority") == dict(AUTHORITY),
             "pinned full-period diagnostic changed or gained authority")
    inv = inspect_official_issuer_xlsx(raw)
    sha = hashlib.sha256(raw).hexdigest()
    report = {
        "contract": CONTRACT,
        "status": "US_ISSUER_WORKBOOK_CAPTURED_LAYOUT_ONLY_NO_PIT",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "pinned_prior_diagnostic_sha256": PREVIOUS_GRID.sha256,
        "pinned_prior_diagnostic_fingerprint": PREVIOUS_GRID.fingerprint,
        "source_url": ISSUER_URL,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "acquisition_method": acquisition_method,
        "original_xlsx_sha256": sha,
        "original_xlsx_bytes": len(raw),
        **inv,
        "issuer_table_is_final_authority_on_asof_history": False,
        "issuer_original_publication_clock_proved": False,
        "historical_revision_clock_proved": False,
        "entire_historical_dividend_series_reconciled": False,
        "split_and_noncash_coverage_qualified": False,
        "historical_economic_returns_qualified": False,
        "forecast_total_variance": None,
        "option_inputs_accepted": False,
        "pilot_input_acceptance": False,
        "historical_performance_evidence": False,
        "source_requests": {"issuer_document_gets": int(acquisition_method == "EXPLICIT_ONE_GET"),
                            "paid_market_data": 0, "broker": 0, "stock_prices": 0,
                            "options": 0, "outcomes": 0},
        "authority": dict(AUTHORITY),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
