from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.enums import SessionSegment
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_close import (
    CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
    StockExitTriggerDisposition,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.case_file import (
    EvidenceAvailability,
    GeometryStatus,
    InstrumentKind as CaseInstrumentKind,
    InstrumentSelection,
    NewsContextSummary,
    Phase13CaseFile,
    PortfolioRiskAssessment,
    PortfolioRiskStatus,
    TradeGeometry,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.recurrent_exit_plan import (
    build_recurrent_stock_exit_plan_v1,
)


NOW = datetime(2026, 9, 18, 15, 10, tzinfo=UTC)


def test_current_webull_stock_close_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        == "05c2a9a2ac3d34b73a5ba9ab4fd9192209c98d02731179dbd65cad1aa239a6d3"
    )


def test_exit_disposition_enum_is_frozen() -> None:
    assert tuple(item.value for item in StockExitTriggerDisposition) == (
        "NO_TRIGGER",
        "STOP",
        "TARGET",
    )
