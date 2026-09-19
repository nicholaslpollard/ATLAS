from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import SessionSegment
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_decision_stock_close_contract import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT,
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.execution.current_webull_quote_bundle import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
    CurrentWebullStockQuoteBundleV1,
    CurrentWebullStockQuoteV1,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
    simulated_open_position_fingerprint,
)
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionError,
    apply_recurrent_close_position_batch_v1,
)
from packages.simulation.recurrent_cycle import RecurrentCycleReceiptV1
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanBookV1,
    RecurrentDecisionStockExitPlanV1,
    recurrent_decision_stock_exit_plan_book_from_payload,
    recurrent_decision_stock_exit_plan_from_payload,
)
from packages.simulation.recurrent_exit_fill import (
    RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
    RecurrentExitFillEvidenceV1,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
)


CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID = (
    "atlas-current-webull-decision-stock-close/current.json"
)
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024
_TOLERANCE = 1e-9


class CurrentWebullDecisionStockCloseEvidenceError(RuntimeError):
    pass


class StockExitTriggerDisposition(StrEnum):
    NO_TRIGGER = "NO_TRIGGER"
    STOP = "STOP"
    TARGET = "TARGET"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=_TOLERANCE,
    )


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: object) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_plan_position(
    plan: RecurrentDecisionStockExitPlanV1,
    position: SimulatedOpenPositionV1,
) -> None:
    if simulated_open_position_fingerprint(position) != plan.position_fingerprint:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "exit plan position fingerprint does not match current open position"
        )
    checks = (
        (
            position.decision_record_fingerprint,
            plan.decision_record_fingerprint,
            "decision record",
        ),
        (
            position.candidate_fingerprint,
            plan.candidate_fingerprint,
            "candidate",
        ),
        (
            position.instrument_id,
            plan.instrument_id,
            "instrument id",
        ),
        (position.ticker, plan.ticker, "ticker"),
        (position.direction, plan.direction, "direction"),
        (position.opened_utc, plan.opened_utc, "opened time"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"exit plan {label} does not match current open position"
            )
    if not _same(
        position.entry_price_per_unit,
        plan.actual_entry_price_per_unit,
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "exit plan entry price does not match current open position"
        )


def _fill_source_fingerprint(
    *,
    plan_book_fingerprint: str,
    quote_bundle_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    plan: RecurrentDecisionStockExitPlanV1,
    quote: CurrentWebullStockQuoteV1,
    disposition: StockExitTriggerDisposition,
    explicit_exit_fee_dollars: float,
) -> str:
    return _fingerprint_payload(
        {
            "contract_fingerprint": (
                CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
            ),
            "plan_book_fingerprint": plan_book_fingerprint,
            "quote_bundle_fingerprint": quote_bundle_fingerprint,
            "fee_source_id": fee_source_id,
            "fee_source_fingerprint": fee_source_fingerprint,
            "plan_fingerprint": plan.plan_fingerprint,
            "quote": quote,
            "disposition": disposition,
            "explicit_exit_fee_dollars": explicit_exit_fee_dollars,
        }
    )


@dataclass(frozen=True)
class CurrentWebullDecisionStockCloseTriggerV1:
    plan: RecurrentDecisionStockExitPlanV1
    quote: CurrentWebullStockQuoteV1
    disposition: StockExitTriggerDisposition
    explicit_exit_fee_dollars: float | None
    fill: RecurrentExitFillEvidenceV1 | None

    time_exit_evaluated: bool = False
    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.plan.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "close trigger exit-plan contract fingerprint mismatch"
            )
        if self.quote.symbol != self.plan.ticker:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "close trigger quote/plan ticker mismatch"
            )
        if self.quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "close trigger quote must be regular-session"
            )
        bid = self.quote.bid_price
        if self.disposition == StockExitTriggerDisposition.NO_TRIGGER:
            if not (
                self.plan.stop_price_per_unit
                < bid
                < self.plan.target_price_per_unit
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "NO_TRIGGER bid must remain strictly between stop and target"
                )
            if (
                self.explicit_exit_fee_dollars is not None
                or self.fill is not None
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "NO_TRIGGER cannot carry fee or exit fill"
                )
        else:
            if self.explicit_exit_fee_dollars is None:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "triggered close requires explicit exit fee"
                )
            if (
                not math.isfinite(self.explicit_exit_fee_dollars)
                or self.explicit_exit_fee_dollars < 0.0
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "triggered exit fee must be finite and nonnegative"
                )
            if self.fill is None:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "triggered close requires recurrent exit-fill evidence"
                )
            if (
                self.fill.contract_fingerprint
                != RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "triggered close fill contract fingerprint mismatch"
                )
            if self.disposition == StockExitTriggerDisposition.STOP:
                if bid > self.plan.stop_price_per_unit:
                    raise CurrentWebullDecisionStockCloseEvidenceError(
                        "STOP trigger requires bid at or below stop"
                    )
            elif self.disposition == StockExitTriggerDisposition.TARGET:
                if bid < self.plan.target_price_per_unit:
                    raise CurrentWebullDecisionStockCloseEvidenceError(
                        "TARGET trigger requires bid at or above target"
                    )
            else:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "unsupported stock exit trigger disposition"
                )
            fill = self.fill
            if fill.position_fingerprint != self.plan.position_fingerprint:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "close fill position does not match exit plan"
                )
            if fill.ticker != self.quote.symbol:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "close fill ticker does not match quote"
                )
            if fill.exited_utc != self.quote.received_at_utc:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "close fill timestamp must equal quote receipt"
                )
            if not _same(fill.exit_price_per_unit, bid):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "long-stock exit fill price must equal executable bid"
                )
            if not _same(
                fill.exit_fees_dollars,
                self.explicit_exit_fee_dollars,
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "close fill fee does not match explicit fee evidence"
                )

        if (
            self.time_exit_evaluated
            or self.provider_calls_performed
            or self.broker_calls_performed
            or self.broker_fill_authority
            or self.order_creation_authority
            or self.paper_authority
            or self.live_authority
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "close trigger cannot claim time-exit, network, broker-fill, order, or trading authority"
            )

    @property
    def trigger_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _bundle_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    source_recurrent_state_fingerprint: str,
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
    fee_source_id: str | None,
    fee_source_fingerprint: str | None,
    built_at_utc: datetime,
    triggers: tuple[CurrentWebullDecisionStockCloseTriggerV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        "source_id": CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "exit_plan_book": exit_plan_book,
        "quote_bundle": quote_bundle,
        "fee_source_id": fee_source_id,
        "fee_source_fingerprint": fee_source_fingerprint,
        "built_at_utc": built_at_utc,
        "triggers": triggers,
        "provider_calls_performed": 0,
        "broker_calls_performed": 0,
        "provider_read_authority": False,
        "provider_write_authority": False,
        "broker_read_authority": False,
        "broker_write_authority": False,
        "broker_fill_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class CurrentWebullDecisionStockCloseEvidenceBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    cycle_id: str
    cycle_fingerprint: str
    source_recurrent_state_fingerprint: str
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None
    fee_source_id: str | None
    fee_source_fingerprint: str | None
    built_at_utc: datetime
    triggers: tuple[CurrentWebullDecisionStockCloseTriggerV1, ...]

    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "current Webull decision CLOSE contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "current Webull decision CLOSE contract fingerprint mismatch"
            )
        if (
            self.source_id
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "current Webull decision CLOSE source id mismatch"
            )
        for label, value in (
            ("bundle", self.bundle_fingerprint),
            ("cycle", self.cycle_fingerprint),
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        if (
            self.exit_plan_book.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE exit-plan book contract fingerprint mismatch"
            )
        if (
            self.exit_plan_book.source_recurrent_state_fingerprint
            != self.source_recurrent_state_fingerprint
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE exit-plan book is bound to a different recurrent state"
            )

        built = _require_aware(
            self.built_at_utc,
            label="current Webull decision CLOSE build time",
        )
        ordered = tuple(
            sorted(
                self.triggers,
                key=lambda item: item.plan.position_fingerprint,
            )
        )
        if ordered != self.triggers:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE triggers must be ordered by position fingerprint"
            )
        trigger_plans = tuple(
            trigger.plan for trigger in self.triggers
        )
        if trigger_plans != self.exit_plan_book.plans:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE triggers must exactly cover the exit-plan book"
            )
        ids = tuple(
            trigger.plan.position_fingerprint
            for trigger in self.triggers
        )
        if len(ids) != len(set(ids)):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE bundle cannot duplicate positions"
            )

        if self.triggers:
            if self.quote_bundle is None:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "open-position CLOSE evidence requires a quote bundle"
                )
            if (
                self.quote_bundle.contract_fingerprint
                != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "CLOSE quote-bundle contract fingerprint mismatch"
                )
            if self.quote_bundle.captured_at_utc > built:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "CLOSE quote-bundle capture cannot postdate bundle build"
                )
            expected_symbols = tuple(
                sorted(
                    {
                        trigger.plan.ticker
                        for trigger in self.triggers
                    }
                )
            )
            if self.quote_bundle.requested_symbols != expected_symbols:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "CLOSE quote-bundle symbols do not match plan coverage"
                )
            quotes = {
                quote.symbol: quote
                for quote in self.quote_bundle.quotes
            }
            for trigger in self.triggers:
                if quotes.get(trigger.plan.ticker) != trigger.quote:
                    raise CurrentWebullDecisionStockCloseEvidenceError(
                        "CLOSE trigger quote does not match retained quote bundle"
                    )
        elif self.quote_bundle is not None:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "empty CLOSE cannot claim quote-bundle evidence"
            )

        has_triggered_fill = any(
            trigger.fill is not None for trigger in self.triggers
        )
        if has_triggered_fill:
            if (
                self.fee_source_id is None
                or not self.fee_source_id.strip()
                or self.fee_source_fingerprint is None
            ):
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "triggered CLOSE requires explicit fee-source evidence"
                )
            _require_sha(
                self.fee_source_fingerprint,
                label="CLOSE fee source",
            )
        elif (
            self.fee_source_id is not None
            or self.fee_source_fingerprint is not None
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE without triggered fills must not claim fee-source evidence"
            )

        quote_bundle_fp = (
            None
            if self.quote_bundle is None
            else self.quote_bundle.bundle_fingerprint
        )
        for trigger in self.triggers:
            if trigger.quote.received_at_utc > built:
                raise CurrentWebullDecisionStockCloseEvidenceError(
                    "CLOSE trigger quote cannot postdate bundle build"
                )
            if trigger.fill is not None:
                if (
                    trigger.fill.source_recurrent_state_fingerprint
                    != self.source_recurrent_state_fingerprint
                ):
                    raise CurrentWebullDecisionStockCloseEvidenceError(
                        "CLOSE fill is bound to a different recurrent state"
                    )
                assert quote_bundle_fp is not None
                assert self.fee_source_id is not None
                assert self.fee_source_fingerprint is not None
                expected_source = _fill_source_fingerprint(
                    plan_book_fingerprint=(
                        self.exit_plan_book.book_fingerprint
                    ),
                    quote_bundle_fingerprint=quote_bundle_fp,
                    fee_source_id=self.fee_source_id,
                    fee_source_fingerprint=(
                        self.fee_source_fingerprint
                    ),
                    plan=trigger.plan,
                    quote=trigger.quote,
                    disposition=trigger.disposition,
                    explicit_exit_fee_dollars=(
                        trigger.explicit_exit_fee_dollars or 0.0
                    ),
                )
                if (
                    trigger.fill.fill_source_fingerprint
                    != expected_source
                ):
                    raise CurrentWebullDecisionStockCloseEvidenceError(
                        "CLOSE fill source fingerprint mismatch"
                    )

        if any(
            (
                self.provider_calls_performed,
                self.broker_calls_performed,
                self.provider_read_authority,
                self.provider_write_authority,
                self.broker_read_authority,
                self.broker_write_authority,
                self.broker_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE evidence bundle cannot grant external or trading authority"
            )

        expected = _fingerprint_payload(
            _bundle_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                exit_plan_book=self.exit_plan_book,
                quote_bundle=self.quote_bundle,
                fee_source_id=self.fee_source_id,
                fee_source_fingerprint=self.fee_source_fingerprint,
                built_at_utc=built,
                triggers=self.triggers,
            )
        )
        if self.bundle_fingerprint != expected:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "CLOSE evidence bundle self-fingerprint mismatch"
            )

    @property
    def triggered_fills(
        self,
    ) -> tuple[RecurrentExitFillEvidenceV1, ...]:
        return tuple(
            trigger.fill
            for trigger in self.triggers
            if trigger.fill is not None
        )


def build_current_webull_decision_stock_close_evidence_bundle_v1(
    *,
    account: RecurrentLifecycleAccountV1,
    identity: RecurrentCycleRunIdentityV1,
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
    explicit_exit_fees_by_position: Mapping[str, float],
    fee_source_id: str | None = None,
    fee_source_fingerprint: str | None = None,
    built_at_utc: datetime | None = None,
) -> CurrentWebullDecisionStockCloseEvidenceBundleV1:
    state = account.state
    if (
        state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "source recurrent account contract fingerprint mismatch"
        )
    if (
        state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(state)
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "source recurrent state fingerprint mismatch"
        )
    if (
        exit_plan_book.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "exit-plan book contract fingerprint mismatch"
        )
    if (
        exit_plan_book.source_recurrent_state_fingerprint
        != state.state_fingerprint
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "exit-plan book is stale for current recurrent state"
        )

    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="current Webull decision CLOSE build time",
    )
    if built < state.as_of_utc:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "CLOSE evidence cannot predate recurrent state"
        )

    positions = tuple(state.open_positions)
    if any(
        position.instrument_kind != InstrumentKind.STOCK
        for position in positions
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE v1 cannot evaluate option positions"
        )
    if any(
        position.direction != DiscoveryDirection.BULLISH
        for position in positions
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE v1 supports bullish stock longs only"
        )

    positions_by_fp = {
        position.position_fingerprint: position
        for position in positions
    }
    plans_by_fp = {
        plan.position_fingerprint: plan
        for plan in exit_plan_book.plans
    }
    if set(positions_by_fp) != set(plans_by_fp):
        missing = sorted(set(positions_by_fp) - set(plans_by_fp))
        extra = sorted(set(plans_by_fp) - set(positions_by_fp))
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "exit-plan coverage must exactly match current open positions; "
            f"missing={missing}, extra={extra}"
        )
    for position_fp, position in positions_by_fp.items():
        _validate_plan_position(plans_by_fp[position_fp], position)

    if not positions:
        if quote_bundle is not None:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "empty CLOSE must not claim quote capture"
            )
        if explicit_exit_fees_by_position:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "empty CLOSE cannot carry exit-fee evidence"
            )
        if fee_source_id is not None or fee_source_fingerprint is not None:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "empty CLOSE cannot carry fee-source evidence"
            )
        payload = _bundle_payload(
            cycle_id=identity.cycle_id,
            cycle_fingerprint=identity.cycle_fingerprint,
            source_recurrent_state_fingerprint=state.state_fingerprint,
            exit_plan_book=exit_plan_book,
            quote_bundle=None,
            fee_source_id=None,
            fee_source_fingerprint=None,
            built_at_utc=built,
            triggers=(),
        )
        return CurrentWebullDecisionStockCloseEvidenceBundleV1(
            contract_version=(
                CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
            ),
            contract_fingerprint=(
                CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
            ),
            source_id=(
                CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID
            ),
            bundle_fingerprint=_fingerprint_payload(payload),
            cycle_id=identity.cycle_id,
            cycle_fingerprint=identity.cycle_fingerprint,
            source_recurrent_state_fingerprint=state.state_fingerprint,
            exit_plan_book=exit_plan_book,
            quote_bundle=None,
            fee_source_id=None,
            fee_source_fingerprint=None,
            built_at_utc=built,
            triggers=(),
        )

    if quote_bundle is None:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "open stock positions require current Webull quote evidence"
        )
    if (
        quote_bundle.contract_fingerprint
        != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "quote bundle contract fingerprint mismatch"
        )
    if quote_bundle.captured_at_utc > built:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "Webull CLOSE quote-bundle capture postdates build time"
        )
    current_tickers = tuple(
        sorted({position.ticker for position in positions})
    )
    if quote_bundle.requested_symbols != current_tickers:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "Webull quote bundle symbols must exactly match current open-stock tickers"
        )
    quotes = {
        quote.symbol: quote for quote in quote_bundle.quotes
    }

    preliminary: list[
        tuple[
            RecurrentDecisionStockExitPlanV1,
            CurrentWebullStockQuoteV1,
            StockExitTriggerDisposition,
        ]
    ] = []
    for position_fp in sorted(positions_by_fp):
        position = positions_by_fp[position_fp]
        plan = plans_by_fp[position_fp]
        quote = quotes.get(position.ticker)
        if quote is None:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"missing exact-case Webull quote for {position.ticker}"
            )
        if quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"Webull CLOSE quote is outside regular session for {position.ticker}"
            )
        if quote.received_at_utc < state.as_of_utc:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"Webull CLOSE quote predates recurrent state for {position.ticker}"
            )
        provider_age = (
            built - quote.provider_timestamp_utc
        ).total_seconds()
        receive_age = (
            built - quote.received_at_utc
        ).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"Webull CLOSE quote is ahead of build time for {position.ticker}"
            )
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"Webull CLOSE quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap for {position.ticker}"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"Webull CLOSE quote receipt is stale for {position.ticker}"
            )

        bid = quote.bid_price
        if bid <= plan.stop_price_per_unit:
            disposition = StockExitTriggerDisposition.STOP
        elif bid >= plan.target_price_per_unit:
            disposition = StockExitTriggerDisposition.TARGET
        else:
            disposition = StockExitTriggerDisposition.NO_TRIGGER
        preliminary.append((plan, quote, disposition))

    triggered_position_fps = {
        plan.position_fingerprint
        for plan, _quote, disposition in preliminary
        if disposition != StockExitTriggerDisposition.NO_TRIGGER
    }
    supplied_fee_keys = set(explicit_exit_fees_by_position)
    if supplied_fee_keys != triggered_position_fps:
        missing = sorted(
            triggered_position_fps - supplied_fee_keys
        )
        extra = sorted(
            supplied_fee_keys - triggered_position_fps
        )
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "explicit exit fee coverage must exactly match triggered positions; "
            f"missing={missing}, extra={extra}"
        )

    if triggered_position_fps:
        if (
            fee_source_id is None
            or not fee_source_id.strip()
            or fee_source_fingerprint is None
        ):
            raise CurrentWebullDecisionStockCloseEvidenceError(
                "triggered CLOSE requires explicit fee-source evidence"
            )
        _require_sha(
            fee_source_fingerprint,
            label="explicit exit fee source",
        )
    elif (
        fee_source_id is not None
        or fee_source_fingerprint is not None
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "NO_TRIGGER CLOSE must not claim fee-source evidence"
        )

    triggers: list[CurrentWebullDecisionStockCloseTriggerV1] = []
    for plan, quote, disposition in preliminary:
        if disposition == StockExitTriggerDisposition.NO_TRIGGER:
            triggers.append(
                CurrentWebullDecisionStockCloseTriggerV1(
                    plan=plan,
                    quote=quote,
                    disposition=disposition,
                    explicit_exit_fee_dollars=None,
                    fill=None,
                )
            )
            continue

        fee = float(
            explicit_exit_fees_by_position[
                plan.position_fingerprint
            ]
        )
        if not math.isfinite(fee) or fee < 0.0:
            raise CurrentWebullDecisionStockCloseEvidenceError(
                f"explicit exit fee must be finite and nonnegative for {plan.ticker}"
            )
        assert fee_source_id is not None
        assert fee_source_fingerprint is not None
        source_fp = _fill_source_fingerprint(
            plan_book_fingerprint=exit_plan_book.book_fingerprint,
            quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
            fee_source_id=fee_source_id,
            fee_source_fingerprint=fee_source_fingerprint,
            plan=plan,
            quote=quote,
            disposition=disposition,
            explicit_exit_fee_dollars=fee,
        )
        fill = build_recurrent_exit_fill_evidence(
            source_state=state,
            position_fingerprint=plan.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    f"current-webull-decision-stock-close:{plan.ticker}:{disposition.value}"
                ),
                fill_source_fingerprint=source_fp,
                exited_utc=quote.received_at_utc,
                exit_price_per_unit=quote.bid_price,
                explicit_exit_fees_dollars=fee,
            ),
        )
        triggers.append(
            CurrentWebullDecisionStockCloseTriggerV1(
                plan=plan,
                quote=quote,
                disposition=disposition,
                explicit_exit_fee_dollars=fee,
                fill=fill,
            )
        )

    ordered = tuple(
        sorted(
            triggers,
            key=lambda item: item.plan.position_fingerprint,
        )
    )
    fills = tuple(
        trigger.fill
        for trigger in ordered
        if trigger.fill is not None
    )
    try:
        apply_recurrent_close_position_batch_v1(
            account,
            fills,
        )
    except RecurrentClosePositionError as exc:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull CLOSE batch dry-run failed"
        ) from exc

    payload = _bundle_payload(
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        exit_plan_book=exit_plan_book,
        quote_bundle=quote_bundle,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )
    return CurrentWebullDecisionStockCloseEvidenceBundleV1(
        contract_version=(
            CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        source_id=(
            CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID
        ),
        bundle_fingerprint=_fingerprint_payload(payload),
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        exit_plan_book=exit_plan_book,
        quote_bundle=quote_bundle,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )


def current_webull_decision_stock_close_evidence_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_decision_stock_close_evidence_file()


def _fill_from_payload(
    payload: dict[str, object],
) -> RecurrentExitFillEvidenceV1:
    values = dict(payload)
    values["instrument_kind"] = InstrumentKind(
        str(values["instrument_kind"])
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["exited_utc"] = datetime.fromisoformat(
        str(values["exited_utc"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentExitFillEvidenceV1(**values)


def write_current_webull_decision_stock_close_evidence_bundle_v1(
    settings: AtlasSettings,
    bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
) -> Path:
    path = current_webull_decision_stock_close_evidence_path(
        settings
    )
    raw = json.dumps(
        _canonicalize(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_current_webull_decision_stock_close_evidence_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE readback verification mismatch"
        )
    return path


def read_current_webull_decision_stock_close_evidence_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> CurrentWebullDecisionStockCloseEvidenceBundleV1:
    target = (
        Path(path)
        if path is not None
        else current_webull_decision_stock_close_evidence_path(
            settings
        )
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact root must be an object"
        )

    try:
        exit_plan_book = (
            recurrent_decision_stock_exit_plan_book_from_payload(
                dict(payload["exit_plan_book"])
            )
        )
        quote_bundle = (
            None
            if payload.get("quote_bundle") is None
            else CurrentWebullStockQuoteBundleV1.model_validate(
                payload["quote_bundle"]
            )
        )
        triggers = tuple(
            CurrentWebullDecisionStockCloseTriggerV1(
                plan=recurrent_decision_stock_exit_plan_from_payload(
                    dict(item["plan"])
                ),
                quote=CurrentWebullStockQuoteV1.model_validate(
                    item["quote"]
                ),
                disposition=StockExitTriggerDisposition(
                    str(item["disposition"])
                ),
                explicit_exit_fee_dollars=(
                    None
                    if item.get("explicit_exit_fee_dollars") is None
                    else float(item["explicit_exit_fee_dollars"])
                ),
                fill=(
                    None
                    if item.get("fill") is None
                    else _fill_from_payload(
                        dict(item["fill"])
                    )
                ),
                time_exit_evaluated=bool(
                    item["time_exit_evaluated"]
                ),
                provider_calls_performed=int(
                    item["provider_calls_performed"]
                ),
                broker_calls_performed=int(
                    item["broker_calls_performed"]
                ),
                broker_fill_authority=bool(
                    item["broker_fill_authority"]
                ),
                order_creation_authority=bool(
                    item["order_creation_authority"]
                ),
                paper_authority=bool(item["paper_authority"]),
                live_authority=bool(item["live_authority"]),
            )
            for item in payload["triggers"]
        )
        return CurrentWebullDecisionStockCloseEvidenceBundleV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            bundle_fingerprint=str(
                payload["bundle_fingerprint"]
            ),
            cycle_id=str(payload["cycle_id"]),
            cycle_fingerprint=str(
                payload["cycle_fingerprint"]
            ),
            source_recurrent_state_fingerprint=str(
                payload["source_recurrent_state_fingerprint"]
            ),
            exit_plan_book=exit_plan_book,
            quote_bundle=quote_bundle,
            fee_source_id=(
                None
                if payload.get("fee_source_id") is None
                else str(payload["fee_source_id"])
            ),
            fee_source_fingerprint=(
                None
                if payload.get("fee_source_fingerprint") is None
                else str(payload["fee_source_fingerprint"])
            ),
            built_at_utc=datetime.fromisoformat(
                str(payload["built_at_utc"])
            ),
            triggers=triggers,
            provider_calls_performed=int(
                payload["provider_calls_performed"]
            ),
            broker_calls_performed=int(
                payload["broker_calls_performed"]
            ),
            provider_read_authority=bool(
                payload["provider_read_authority"]
            ),
            provider_write_authority=bool(
                payload["provider_write_authority"]
            ),
            broker_read_authority=bool(
                payload["broker_read_authority"]
            ),
            broker_write_authority=bool(
                payload["broker_write_authority"]
            ),
            broker_fill_authority=bool(
                payload["broker_fill_authority"]
            ),
            order_creation_authority=bool(
                payload["order_creation_authority"]
            ),
            paper_authority=bool(payload["paper_authority"]),
            live_authority=bool(payload["live_authority"]),
            promotion_authority=bool(
                payload["promotion_authority"]
            ),
            confluence_authority=bool(
                payload["confluence_authority"]
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        CurrentWebullDecisionStockCloseEvidenceError,
    ) as exc:
        if isinstance(
            exc,
            CurrentWebullDecisionStockCloseEvidenceError,
        ):
            raise
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE artifact failed typed validation"
        ) from exc


def apply_current_webull_decision_stock_close_evidence_bundle_v1(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullDecisionStockCloseEvidenceError(
            "current Webull decision CLOSE bundle is bound to a different cycle"
        )
    return runner.apply_close(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        fills=bundle.triggered_fills,
        now_utc=now_utc,
    )


__all__ = [
    "CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION",
    "CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_SOURCE_ID",
    "CurrentWebullDecisionStockCloseEvidenceBundleV1",
    "CurrentWebullDecisionStockCloseEvidenceError",
    "CurrentWebullDecisionStockCloseTriggerV1",
    "StockExitTriggerDisposition",
    "apply_current_webull_decision_stock_close_evidence_bundle_v1",
    "build_current_webull_decision_stock_close_evidence_bundle_v1",
    "current_webull_decision_stock_close_evidence_path",
    "read_current_webull_decision_stock_close_evidence_bundle_v1",
    "write_current_webull_decision_stock_close_evidence_bundle_v1",
]
