"""ATLAS storage layer.

Keep package initialization lightweight.

Submodules in :mod:`packages.data` are used by aggregation and materialization
code in both directions.  Eagerly importing the materializer here creates a
cycle such as::

    aggregation.bar_builder -> data.atomic -> data.__init__
      -> data.materializer -> aggregation.bar_builder

The public convenience exports therefore use PEP 562 lazy attribute loading.
Importing a low-level module such as ``packages.data.atomic`` no longer pulls
in the materialization stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .paths import MarketDataPaths

if TYPE_CHECKING:  # pragma: no cover - type-checker only
    from .duckdb_repository import DuckDBMarketRepository
    from .materializer import MarketDataMaterializer, MaterializationResult

__all__ = [
    "MarketDataPaths",
    "MarketDataMaterializer",
    "MaterializationResult",
    "DuckDBMarketRepository",
]


def __getattr__(name: str) -> Any:
    """Lazily expose higher-level storage classes without import cycles."""
    if name in {"MarketDataMaterializer", "MaterializationResult"}:
        from .materializer import MarketDataMaterializer, MaterializationResult

        exports = {
            "MarketDataMaterializer": MarketDataMaterializer,
            "MaterializationResult": MaterializationResult,
        }
        return exports[name]

    if name == "DuckDBMarketRepository":
        from .duckdb_repository import DuckDBMarketRepository

        return DuckDBMarketRepository

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
