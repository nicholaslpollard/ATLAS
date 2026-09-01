from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from packages.core.settings import AtlasSettings
from packages.instruments.identity import InstrumentIdentityResolver
from packages.providers.massive.reference_data import MassiveReferenceProvider

from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_PROTECTED_END,
    required_lag_reference_dates,
)


MOMSEASON_SOURCE_ROOT_RELATIVE = Path(
    "strategy_evaluation/literature_anchored/momseason/v1/source"
)
MASSIVE_SPLITS_ENDPOINT = "/stocks/v1/splits"
MASSIVE_DIVIDENDS_ENDPOINT = "/stocks/v1/dividends"
MASSIVE_ACTION_PAGE_LIMIT = 5000


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def write_gzip_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with gzip.open(temp, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")
            count += 1
    temp.replace(path)
    return count


def read_gzip_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


class MomSeasonSourceAcquirer:
    """Acquire source-only LIT-01 evidence into an isolated research cache.

    This class never reads a target-month return and never writes provider, broker,
    PAPER, LIVE, strategy, discovery, regime, or authority state.  Historical
    reference snapshots are needed because ATLAS daily flat-file rows are keyed by
    ticker while the literature signal must follow a stable security identity.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        reference_provider: MassiveReferenceProvider | None = None,
    ) -> None:
        self.settings = settings
        self.reference_provider = reference_provider or MassiveReferenceProvider(settings)
        self.identity = InstrumentIdentityResolver()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / MOMSEASON_SOURCE_ROOT_RELATIVE

    def reference_path(self, as_of_date: date) -> Path:
        return (
            self.root
            / "reference"
            / f"date={as_of_date.isoformat()}"
            / "active_stock_snapshot.jsonl.gz"
        )

    def action_path(self, action: str) -> Path:
        if action not in {"splits", "dividends"}:
            raise ValueError(f"unsupported LIT-01 corporate action source: {action}")
        return self.root / "corporate_actions" / f"{action}.jsonl.gz"

    def acquire_reference_date(
        self,
        as_of_date: date,
        *,
        force: bool = False,
    ) -> dict[str, object]:
        target = self.reference_path(as_of_date)
        if target.is_file() and not force:
            return {
                "as_of_date": as_of_date.isoformat(),
                "path": str(target),
                "skipped": True,
                "row_count": len(read_gzip_jsonl(target)),
            }

        raw = self.reference_provider.stock_snapshot(as_of_date, include_inactive=False)
        rows: list[dict[str, object]] = []
        for item in raw:
            instrument_id, identity_key, quality = self.identity.resolve(item, as_of_date)
            rows.append(
                {
                    "as_of_date": as_of_date.isoformat(),
                    "instrument_id": instrument_id,
                    "identity_key": identity_key,
                    "identity_quality": quality.value,
                    "ticker": str(item.get("ticker") or ""),
                    "composite_figi": item.get("composite_figi"),
                    "share_class_figi": item.get("share_class_figi"),
                    "cik": item.get("cik"),
                    "primary_exchange": item.get("primary_exchange"),
                    "security_type": item.get("type"),
                    "active": bool(item.get("active", True)),
                }
            )
        rows.sort(key=lambda row: (str(row["instrument_id"]), str(row["ticker"])))
        count = write_gzip_jsonl(target, rows)
        return {
            "as_of_date": as_of_date.isoformat(),
            "path": str(target),
            "skipped": False,
            "row_count": count,
        }

    def _action_rows(
        self,
        *,
        endpoint: str,
        date_field: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        params = {
            f"{date_field}.gte": start_date.isoformat(),
            f"{date_field}.lte": end_date.isoformat(),
            "limit": MASSIVE_ACTION_PAGE_LIMIT,
            "sort": f"{date_field}.asc",
        }
        rows: list[dict[str, object]] = []
        for page in self.reference_provider.client.iter_pages(endpoint, params):
            values = page.get("results") or []
            if not isinstance(values, list):
                raise ValueError(f"Massive action response for {endpoint} has non-list results")
            for value in values:
                if isinstance(value, dict):
                    rows.append(dict(value))
        rows.sort(
            key=lambda row: (
                str(row.get(date_field) or ""),
                str(row.get("ticker") or ""),
                str(row.get("id") or ""),
            )
        )
        return rows

    def acquire_corporate_actions(self, *, force: bool = False) -> dict[str, object]:
        required_dates = required_lag_reference_dates()
        start_date = min(required_dates)
        end_date = LITERATURE_MOMSEASON_PROTECTED_END
        configs = (
            ("splits", MASSIVE_SPLITS_ENDPOINT, "execution_date"),
            ("dividends", MASSIVE_DIVIDENDS_ENDPOINT, "ex_dividend_date"),
        )
        result: dict[str, object] = {}
        for name, endpoint, date_field in configs:
            target = self.action_path(name)
            if target.is_file() and not force:
                rows = read_gzip_jsonl(target)
                result[name] = {
                    "path": str(target),
                    "skipped": True,
                    "row_count": len(rows),
                }
                continue
            rows = self._action_rows(
                endpoint=endpoint,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
            )
            count = write_gzip_jsonl(target, rows)
            result[name] = {
                "path": str(target),
                "skipped": False,
                "row_count": count,
            }
        return result

    def acquire(self, *, force: bool = False) -> dict[str, object]:
        required = required_lag_reference_dates()
        references: list[dict[str, object]] = []
        for index, as_of_date in enumerate(required, start=1):
            item = self.acquire_reference_date(as_of_date, force=force)
            references.append(item)
            print(
                "LIT-01 historical reference acquisition: "
                f"{index}/{len(required)} date={as_of_date} rows={item['row_count']} "
                f"skipped={item['skipped']}"
            )
        actions = self.acquire_corporate_actions(force=force)
        return {
            "reference_dates": len(required),
            "reference_results": references,
            "corporate_actions": actions,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
