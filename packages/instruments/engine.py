from __future__ import annotations

from datetime import date
from typing import Any

from packages.instruments.option_filter import rank_option_alternatives
from packages.portfolio.phase13_policy import PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED
from packages.schemas.case_file import EvidenceAvailability, InstrumentKind, InstrumentSelection
from packages.schemas.discovery_score import DiscoveryDirection


class Phase13InstrumentError(ValueError):
    pass


def build_instrument_selection(
    *,
    ticker: str,
    as_of_date: date,
    direction: DiscoveryDirection,
    option_snapshot_items: list[dict[str, Any]] | None,
    option_snapshot_path: str | None = None,
    option_snapshot_sha256: str | None = None,
) -> InstrumentSelection:
    symbol = ticker.strip()
    if not symbol:
        raise Phase13InstrumentError("ticker cannot be blank")
    if PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED:
        raise Phase13InstrumentError(
            "Phase 13 v1 assumes no accepted option relative-value model; policy version must change"
        )

    if option_snapshot_items is None:
        availability = EvidenceAvailability.UNAVAILABLE
        alternatives = ()
        reasons = (
            "EQUITY_PRIMARY_PHASE13_V1",
            "OPTION_CHAIN_UNAVAILABLE_OR_NOT_ACCESSED",
            "OPTION_NOT_SELECTED_NO_ACCEPTED_RELATIVE_VALUE_MODEL",
        )
        option_snapshot_path = None
        option_snapshot_sha256 = None
    else:
        availability = EvidenceAvailability.AVAILABLE
        alternatives = rank_option_alternatives(
            option_snapshot_items,
            as_of_date=as_of_date,
            direction=direction,
        )
        reasons = (
            "EQUITY_PRIMARY_PHASE13_V1",
            "OPTION_CHAIN_SCREENED_FOR_SUPPORTING_ALTERNATIVES",
            "OPTION_NOT_SELECTED_NO_ACCEPTED_RELATIVE_VALUE_MODEL",
        )

    return InstrumentSelection(
        primary_kind=InstrumentKind.EQUITY,
        primary_ticker=symbol,
        option_chain_availability=availability,
        option_chain_snapshot_path=option_snapshot_path,
        option_chain_snapshot_sha256=option_snapshot_sha256,
        ranked_option_alternatives=alternatives,
        reason_codes=reasons,
    )
