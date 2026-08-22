from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime

from packages.core.enums import LiveFeedMode, SessionSegment
from packages.execution.phase15_policy import (
    PHASE15_EXTENDED_HOURS_ENABLED,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R,
    PHASE15_MAX_QUOTE_AGE_SECONDS,
    PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK,
    PHASE15_REQUIRE_BROKER_PREFLIGHT,
    PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
    PHASE15_REQUIRE_PROFIT_TARGET,
    PHASE15_REQUIRE_PROTECTIVE_STOP,
)
from packages.schemas.case_file import GeometryStatus, InstrumentKind, PortfolioRiskStatus, Phase13CaseFile
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSide,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.live_market import LiveQuote


class ExecutionIntentError(ValueError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def build_execution_intent(
    case: Phase13CaseFile,
    *,
    phase13_case_sha256: str,
    phase14_acceptance_sha256: str,
    quote: LiveQuote,
    environment: ExecutionEnvironment,
    broker: BrokerName,
    now_utc: datetime | None = None,
) -> ExecutionIntent:
    """Translate a Phase 13 reference case into a bounded executable entry plan.

    The accepted stop and target remain fixed. The entry is a marketable regular-hours
    limit at the current NBBO side. Quantity may shrink to preserve the accepted dollar
    risk budget but can never exceed the Phase 13 proposed quantity.
    """

    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    if not case.phase14_review_ready:
        raise ExecutionIntentError("Phase 15 requires a Phase 14 review-ready Phase 13 case")
    if case.geometry.status != GeometryStatus.AVAILABLE:
        raise ExecutionIntentError("Phase 15 requires available deterministic geometry")
    if case.portfolio_risk.status != PortfolioRiskStatus.ADMISSIBLE:
        raise ExecutionIntentError("Phase 15 requires an admissible deterministic risk plan")
    if case.instrument_selection.primary_kind != InstrumentKind.EQUITY:
        raise ExecutionIntentError("Phase 15 v1 executes equity only")
    if quote.symbol != case.ticker:
        raise ExecutionIntentError("execution quote ticker differs from provider-native case ticker")
    if quote.session_segment != SessionSegment.REGULAR:
        raise ExecutionIntentError("Phase 15 v1 entry requires the regular trading session")
    if quote.feed_mode != LiveFeedMode.REALTIME or quote.expected_delay_seconds != 0:
        raise ExecutionIntentError("Phase 15 broker execution requires an undelayed realtime quote")
    if quote.bid_price <= 0.0 or quote.ask_price <= 0.0 or quote.ask_price < quote.bid_price:
        raise ExecutionIntentError("execution quote has invalid NBBO prices")

    quote_age = (now - quote.provider_timestamp_utc.astimezone(UTC)).total_seconds()
    if quote_age < -5.0:
        raise ExecutionIntentError("execution quote timestamp is materially in the future")
    quote_age = max(0.0, quote_age)
    if quote_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
        raise ExecutionIntentError("execution quote is stale")

    environment = ExecutionEnvironment(environment)
    broker = BrokerName(broker)
    if environment == ExecutionEnvironment.LIVE:
        raise ExecutionIntentError("Phase 15 live execution is not promoted")
    if environment == ExecutionEnvironment.SHADOW:
        if broker != BrokerName.SHADOW:
            raise ExecutionIntentError("shadow execution must use the shadow broker")
    elif environment == ExecutionEnvironment.PAPER:
        if broker not in (BrokerName.WEBULL, BrokerName.ALPACA):
            raise ExecutionIntentError("paper execution requires Webull or Alpaca")
    else:
        raise ExecutionIntentError(f"unsupported execution environment: {environment}")

    geometry = case.geometry
    risk = case.portfolio_risk
    if any(
        value is None
        for value in (
            geometry.reference_entry,
            geometry.stop,
            geometry.target,
            risk.proposed_risk_budget,
            risk.proposed_quantity,
        )
    ):
        raise ExecutionIntentError("accepted Phase 13 case is missing executable planning evidence")

    reference_entry = float(geometry.reference_entry)
    stop = float(geometry.stop)
    target = float(geometry.target)
    original_risk = abs(reference_entry - stop)
    if not math.isfinite(original_risk) or original_risk <= 0.0:
        raise ExecutionIntentError("original deterministic risk distance is invalid")

    if case.direction == DiscoveryDirection.BULLISH:
        entry = float(quote.ask_price)
        adverse_drift = max(0.0, entry - reference_entry) / original_risk
        side = BrokerOrderSide.BUY
        executable_risk = entry - stop
        executable_reward = target - entry
    elif case.direction == DiscoveryDirection.BEARISH:
        entry = float(quote.bid_price)
        adverse_drift = max(0.0, reference_entry - entry) / original_risk
        side = BrokerOrderSide.SHORT
        executable_risk = stop - entry
        executable_reward = entry - target
    else:
        raise ExecutionIntentError("neutral cases cannot become execution intents")

    if executable_risk <= 0.0 or executable_reward <= 0.0:
        raise ExecutionIntentError("fresh quote moved outside deterministic stop/target geometry")
    if adverse_drift > PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R + 1e-12:
        raise ExecutionIntentError("fresh quote exceeds preregistered adverse entry drift")
    executable_rr = executable_reward / executable_risk
    if executable_rr < PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK - 1e-12:
        raise ExecutionIntentError("fresh quote reduces executable reward:risk below policy")

    accepted_risk_budget = float(risk.proposed_risk_budget)
    accepted_quantity = int(risk.proposed_quantity)
    by_risk = math.floor(accepted_risk_budget / executable_risk)
    if by_risk < 1:
        raise ExecutionIntentError("accepted dollar risk budget cannot support one executable share")
    executable_quantity = min(accepted_quantity, int(by_risk))

    identity_payload = {
        "phase13_case_sha256": phase13_case_sha256,
        "phase14_acceptance_sha256": phase14_acceptance_sha256,
        "environment": environment.value,
        "broker": broker.value,
        "ticker": case.ticker,
        "quote_provider_timestamp_utc": quote.provider_timestamp_utc.isoformat(),
        "quote_sequence": quote.sequence,
        "entry_limit": entry,
        "quantity": executable_quantity,
        "stop": stop,
        "target": target,
    }
    intent_id = "p15-" + _stable_hash(identity_payload)
    reasons = (
        "ACCEPTED_PHASE14_LINEAGE",
        "PHASE13_REVIEW_READY_DETERMINISTIC_CASE",
        "AI_DISPOSITION_OBSERVATIONAL_NOT_EXECUTION_AUTHORITY",
        "REALTIME_REGULAR_SESSION_QUOTE",
        "ORIGINAL_STOP_TARGET_PRESERVED",
        "ENTRY_ADVERSE_DRIFT_WITHIN_QUARTER_R",
        "EXECUTABLE_QUANTITY_NOT_ABOVE_ACCEPTED_PROPOSAL",
        "BROKER_PREFLIGHT_REQUIRED",
        "BROKER_RECONCILIATION_REQUIRED",
        "LIVE_EXECUTION_NOT_PROMOTED",
    )
    intent = ExecutionIntent(
        intent_id=intent_id,
        instrument_id=case.instrument_id,
        ticker=case.ticker,
        as_of_date=case.as_of_date,
        direction=case.direction,
        environment=environment,
        broker=broker,
        phase13_case_sha256=phase13_case_sha256,
        phase14_acceptance_sha256=phase14_acceptance_sha256,
        reference_entry=reference_entry,
        entry_limit=entry,
        stop=stop,
        target=target,
        original_risk_per_share=original_risk,
        executable_risk_per_share=executable_risk,
        executable_reward_per_share=executable_reward,
        adverse_entry_drift_r=adverse_drift,
        executable_reward_to_risk=executable_rr,
        accepted_risk_budget=accepted_risk_budget,
        accepted_proposed_quantity=accepted_quantity,
        executable_quantity=executable_quantity,
        quote_bid=float(quote.bid_price),
        quote_ask=float(quote.ask_price),
        quote_provider_timestamp_utc=quote.provider_timestamp_utc,
        quote_received_at_utc=quote.received_at_utc,
        quote_feed_mode=_enum_value(quote.feed_mode),
        quote_expected_delay_seconds=int(quote.expected_delay_seconds),
        quote_age_seconds=quote_age,
        session_segment=_enum_value(quote.session_segment),
        order_type="LIMIT",
        time_in_force="DAY",
        extended_hours=PHASE15_EXTENDED_HOURS_ENABLED,
        protective_stop_required=PHASE15_REQUIRE_PROTECTIVE_STOP,
        profit_target_required=PHASE15_REQUIRE_PROFIT_TARGET,
        broker_preflight_required=PHASE15_REQUIRE_BROKER_PREFLIGHT,
        reconciliation_required=PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
        live_execution_enabled=PHASE15_LIVE_EXECUTION_ENABLED,
        reason_codes=reasons,
    )
    expected_side = BrokerOrderSide.BUY if case.direction == DiscoveryDirection.BULLISH else BrokerOrderSide.SHORT
    if side != expected_side:
        raise AssertionError("execution side mapping changed")
    return intent


def build_broker_order_plan(intent: ExecutionIntent) -> BrokerOrderPlan:
    side = (
        BrokerOrderSide.BUY
        if intent.direction == DiscoveryDirection.BULLISH
        else BrokerOrderSide.SHORT
    )
    # 32 chars is the stricter provider limit (Webull). The deterministic intent
    # hash still gives ample collision resistance while keeping the exact same
    # idempotency key valid for Webull and Alpaca.
    client_order_id = "a15-" + intent.intent_id.removeprefix("p15-")[:28]
    return BrokerOrderPlan(
        intent_id=intent.intent_id,
        client_order_id=client_order_id,
        ticker=intent.ticker,
        instrument_type="EQUITY",
        side=side,
        quantity=intent.executable_quantity,
        order_type="LIMIT",
        limit_price=intent.entry_limit,
        stop_price=intent.stop,
        target_price=intent.target,
        time_in_force="DAY",
        extended_hours=False,
        bracket_required=True,
    )
