from __future__ import annotations

from packages.core.enums import DatasetType


DATASET_ALIASES: dict[str, DatasetType] = {
    "minute": DatasetType.STOCK_MINUTE_AGGREGATES,
    "1m": DatasetType.STOCK_MINUTE_AGGREGATES,
    "stock_minute_aggregates": DatasetType.STOCK_MINUTE_AGGREGATES,
    "day": DatasetType.STOCK_DAILY_AGGREGATES,
    "daily": DatasetType.STOCK_DAILY_AGGREGATES,
    "1d": DatasetType.STOCK_DAILY_AGGREGATES,
    "stock_daily_aggregates": DatasetType.STOCK_DAILY_AGGREGATES,
}


def parse_stock_dataset(value: str) -> DatasetType:
    try:
        return DATASET_ALIASES[value.strip().lower()]
    except KeyError as exc:
        choices = ", ".join(sorted(DATASET_ALIASES))
        raise ValueError(f"Unsupported stock flat-file dataset {value!r}. Use one of: {choices}") from exc
