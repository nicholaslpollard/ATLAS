from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


STOOQ_BULK_AUDIT_CONTRACT_VERSION = "historical-source-audit-v2-stooq-bulk-preflight-zip-inspection"
STOOQ_BULK_CANDIDATE_URLS = (
    "https://stooq.com/db/h/d_us_txt.zip",
    "https://static.stooq.com/db/h/d_us_txt.zip",
    "https://static.stooq.com/db/d/d_us_txt.zip",
)
STOOQ_BULK_SAMPLE_BYTES = 4096
STOOQ_BULK_DEFAULT_RELATIVE_PATH = Path("data/cache/stooq/d_us_txt.zip")
STOOQ_SAMPLE_SYMBOLS = ("aapl.us", "spy.us", "nvda.us")


@dataclass(frozen=True, slots=True)
class StooqBulkAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    preflight: tuple[dict[str, object], ...]
    local_zip_path: str
    local_zip_present: bool
    zip_valid: bool | None
    txt_member_count: int | None
    selected_symbols: dict[str, object]
    report_path: str


def _preflight_one(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "User-Agent": "ATLAS-historical-source-audit/1.0",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Range": f"bytes=0-{STOOQ_BULK_SAMPLE_BYTES - 1}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30.0) as response:
            sample = response.read(STOOQ_BULK_SAMPLE_BYTES)
            content_type = response.headers.get("Content-Type", "")
            return {
                "url": url,
                "status": "OK",
                "http_status": int(getattr(response, "status", 200)),
                "content_type": content_type,
                "content_length": response.headers.get("Content-Length"),
                "content_range": response.headers.get("Content-Range"),
                "sample_bytes": len(sample),
                "zip_signature": sample.startswith(b"PK\x03\x04"),
                "html_challenge": b"<html" in sample.lower() or b"requires javascript" in sample.lower(),
                "sample_preview": sample[:160].decode("utf-8", errors="replace") if not sample.startswith(b"PK") else "ZIP_BINARY",
            }
    except HTTPError as exc:
        body = exc.read(STOOQ_BULK_SAMPLE_BYTES)
        return {
            "url": url,
            "status": "HTTP_ERROR",
            "http_status": int(exc.code),
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "sample_bytes": len(body),
            "zip_signature": body.startswith(b"PK\x03\x04"),
            "html_challenge": b"<html" in body.lower() or b"requires javascript" in body.lower(),
            "sample_preview": body[:160].decode("utf-8", errors="replace"),
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "status": "NETWORK_ERROR",
            "http_status": None,
            "message": str(exc),
            "zip_signature": False,
            "html_challenge": False,
        }


def _normalize_member_name(name: str) -> str:
    return name.replace("\\", "/").lower()


def _find_symbol_member(names: list[str], symbol: str) -> str | None:
    target = f"/{symbol.lower()}.txt"
    for name in names:
        normalized = "/" + _normalize_member_name(name).lstrip("/")
        if normalized.endswith(target):
            return name
    return None


def _parse_stooq_txt(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    lines = text.splitlines()
    header = lines[0].strip()
    if header.startswith("<TICKER>"):
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
    fields = ["<TICKER>", "<PER>", "<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<VOL>", "<OPENINT>"]
    reader = csv.DictReader(io.StringIO(text), fieldnames=fields)
    return [dict(row) for row in reader]


def _symbol_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    if not rows:
        return {"rows": 0, "first_date": None, "last_date": None}
    dates = [str(row.get("<DATE>", "")) for row in rows if str(row.get("<DATE>", ""))]
    return {
        "rows": len(rows),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "first_row": rows[0],
        "last_row": rows[-1],
    }


class StooqBulkAudit:
    def __init__(self, settings: AtlasSettings, zip_path: Path | None = None) -> None:
        self.settings = settings
        self.zip_path = (zip_path or (settings.project_root / STOOQ_BULK_DEFAULT_RELATIVE_PATH)).resolve()

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "stooq_bulk_probe.json"

    def run(self) -> StooqBulkAuditReport:
        preflight = tuple(_preflight_one(url) for url in STOOQ_BULK_CANDIDATE_URLS)
        present = self.zip_path.is_file()
        valid: bool | None = None
        member_count: int | None = None
        selected: dict[str, object] = {}
        if present:
            try:
                with zipfile.ZipFile(self.zip_path, "r") as archive:
                    bad = archive.testzip()
                    valid = bad is None
                    names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
                    member_count = len(names)
                    for symbol in STOOQ_SAMPLE_SYMBOLS:
                        member = _find_symbol_member(names, symbol)
                        if member is None:
                            selected[symbol] = {"member": None, "rows": 0, "first_date": None, "last_date": None}
                            continue
                        rows = _parse_stooq_txt(archive.read(member))
                        selected[symbol] = {"member": member, **_symbol_summary(rows)}
            except (zipfile.BadZipFile, OSError) as exc:
                valid = False
                selected["error"] = str(exc)

        report = StooqBulkAuditReport(
            contract_version=STOOQ_BULK_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            preflight=preflight,
            local_zip_path=str(self.zip_path),
            local_zip_present=present,
            zip_valid=valid,
            txt_member_count=member_count,
            selected_symbols=selected,
            report_path=str(self.report_path()),
        )
        atomic_write_text(self.report_path(), json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
