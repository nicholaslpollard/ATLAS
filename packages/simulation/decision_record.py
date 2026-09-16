from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from packages.execution.stock_economics import (
    StockEconomicsInputs,
    StockEconomicsResult,
    build_stock_economic_candidate,
)
from packages.execution.stock_economics_contract import (
    STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
)
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    TradeExpressionDecision,
    TradeExpressionMode,
    select_trade_expression,
)
from packages.execution.trade_expression_contract import (
    TRADE_EXPRESSION_CONTRACT_FINGERPRINT,
)
from packages.schemas.move_time_forecast import (
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT,
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)


SIMULATION_DECISION_RECORD_CONTRACT_VERSION = str(
    SIMULATION_DECISION_RECORD_CONTRACT["contract_id"]
)


class SimulationDecisionRecordError(ValueError):
    pass


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: Any) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def actionability_policy_fingerprint(policy: ActionabilityPolicy) -> str:
    return _fingerprint_payload(policy)


def economic_candidate_fingerprint(candidate: EconomicCandidate) -> str:
    return _fingerprint_payload(candidate)


@dataclass(frozen=True)
class OptionGateReasonLineage:
    identifier: str
    candidate_fingerprint: str
    evaluated: bool
    eligible: bool | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class DecisionReasonLineage:
    stock_economics_reason_codes: tuple[str, ...]
    stock_gate_evaluated: bool
    stock_gate_eligible: bool | None
    stock_gate_reason_codes: tuple[str, ...]
    option_gate_lineage: tuple[OptionGateReasonLineage, ...]
    selection_reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SimulationDecisionRecord:
    contract_version: str
    contract_fingerprint: str
    decision_created_utc: datetime
    forecast_contract_fingerprint: str
    forecast_fingerprint: str
    stock_economics_contract_fingerprint: str
    trade_expression_contract_fingerprint: str
    actionability_policy_fingerprint: str
    trade_expression_mode: TradeExpressionMode
    forecast: UnderlyingMoveTimeForecast
    stock_inputs: StockEconomicsInputs
    stock_economics: StockEconomicsResult
    actionability_policy: ActionabilityPolicy
    option_candidates: tuple[EconomicCandidate, ...]
    option_candidate_fingerprints: tuple[str, ...]
    trade_expression_decision: TradeExpressionDecision
    reason_lineage: DecisionReasonLineage
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != SIMULATION_DECISION_RECORD_CONTRACT_VERSION:
            raise SimulationDecisionRecordError("simulation decision-record contract version mismatch")
        if self.contract_fingerprint != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT:
            raise SimulationDecisionRecordError("simulation decision-record contract fingerprint mismatch")
        if self.forecast_contract_fingerprint != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT:
            raise SimulationDecisionRecordError("forecast contract fingerprint mismatch")
        if self.stock_economics_contract_fingerprint != STOCK_ECONOMICS_CONTRACT_FINGERPRINT:
            raise SimulationDecisionRecordError("stock-economics contract fingerprint mismatch")
        if self.trade_expression_contract_fingerprint != TRADE_EXPRESSION_CONTRACT_FINGERPRINT:
            raise SimulationDecisionRecordError("trade-expression contract fingerprint mismatch")
        if self.forecast_fingerprint != forecast_fingerprint(self.forecast):
            raise SimulationDecisionRecordError("forecast instance fingerprint mismatch")
        if self.actionability_policy_fingerprint != actionability_policy_fingerprint(
            self.actionability_policy
        ):
            raise SimulationDecisionRecordError("actionability policy fingerprint mismatch")
        if self.decision_created_utc.tzinfo is None or self.decision_created_utc.utcoffset() is None:
            raise SimulationDecisionRecordError("decision timestamp must be timezone-aware")
        if self.decision_created_utc < self.forecast.forecast_created_utc:
            raise SimulationDecisionRecordError("decision cannot precede forecast creation")
        if self.trade_expression_decision.mode != self.trade_expression_mode:
            raise SimulationDecisionRecordError("trade-expression mode lineage mismatch")
        expected_option_fingerprints = tuple(
            economic_candidate_fingerprint(candidate) for candidate in self.option_candidates
        )
        if self.option_candidate_fingerprints != expected_option_fingerprints:
            raise SimulationDecisionRecordError("option candidate fingerprint lineage mismatch")
        if any(candidate.kind != InstrumentKind.OPTION for candidate in self.option_candidates):
            raise SimulationDecisionRecordError("decision record option inputs must be OPTION candidates")
        identifiers = [candidate.identifier for candidate in self.option_candidates]
        if len(identifiers) != len(set(identifiers)):
            raise SimulationDecisionRecordError("decision record cannot contain duplicate option identifiers")
        forbidden_authority = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden_authority):
            raise SimulationDecisionRecordError(
                "simulation decision record cannot grant provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def record_fingerprint(self) -> str:
        return simulation_decision_record_fingerprint(self)


def simulation_decision_record_fingerprint(record: SimulationDecisionRecord) -> str:
    return _fingerprint_payload(record)


def simulation_decision_record_payload(record: SimulationDecisionRecord) -> dict[str, Any]:
    payload = _canonicalize(record)
    assert isinstance(payload, dict)
    return {
        **payload,
        "record_fingerprint": simulation_decision_record_fingerprint(record),
    }


def _normalized_option_candidates(
    option_candidates: Sequence[EconomicCandidate],
) -> tuple[EconomicCandidate, ...]:
    for candidate in option_candidates:
        if candidate.kind != InstrumentKind.OPTION:
            raise SimulationDecisionRecordError(
                "option candidate inputs must contain only OPTION candidates"
            )
    identifiers = [candidate.identifier for candidate in option_candidates]
    if len(identifiers) != len(set(identifiers)):
        raise SimulationDecisionRecordError("duplicate option candidate identifiers are not allowed")
    return tuple(
        sorted(
            option_candidates,
            key=lambda candidate: (
                candidate.identifier,
                economic_candidate_fingerprint(candidate),
            ),
        )
    )


def build_simulation_decision_record(
    *,
    decision_created_utc: datetime,
    forecast: UnderlyingMoveTimeForecast,
    stock_inputs: StockEconomicsInputs,
    actionability_policy: ActionabilityPolicy,
    trade_expression_mode: TradeExpressionMode,
    option_candidates: Sequence[EconomicCandidate] = (),
) -> SimulationDecisionRecord:
    """Compose accepted product-side evidence into one immutable simulation record."""

    if decision_created_utc.tzinfo is None or decision_created_utc.utcoffset() is None:
        raise SimulationDecisionRecordError("decision timestamp must be timezone-aware")
    if decision_created_utc < forecast.forecast_created_utc:
        raise SimulationDecisionRecordError("decision cannot precede forecast creation")

    mode = TradeExpressionMode(trade_expression_mode)
    normalized_options = _normalized_option_candidates(option_candidates)
    option_fingerprints = tuple(
        economic_candidate_fingerprint(candidate) for candidate in normalized_options
    )

    stock_economics = build_stock_economic_candidate(
        forecast=forecast,
        inputs=stock_inputs,
    )
    decision = select_trade_expression(
        mode=mode,
        policy=actionability_policy,
        stock_candidate=stock_economics.candidate,
        option_candidates=normalized_options,
    )

    if decision.stock_evaluation is None:
        stock_gate_evaluated = False
        stock_gate_eligible = None
        stock_gate_reasons = ("STOCK_GATE_NOT_EVALUATED_BY_MODE_OR_ABSENT",)
    else:
        stock_gate_evaluated = True
        stock_gate_eligible = decision.stock_evaluation.eligible
        stock_gate_reasons = decision.stock_evaluation.reason_codes

    option_evaluations = {
        evaluation.candidate.identifier: evaluation
        for evaluation in decision.option_evaluations
    }
    option_lineage: list[OptionGateReasonLineage] = []
    for candidate, candidate_fp in zip(normalized_options, option_fingerprints, strict=True):
        evaluation = option_evaluations.get(candidate.identifier)
        if evaluation is None:
            option_lineage.append(
                OptionGateReasonLineage(
                    identifier=candidate.identifier,
                    candidate_fingerprint=candidate_fp,
                    evaluated=False,
                    eligible=None,
                    reason_codes=("OPTION_GATE_NOT_EVALUATED_BY_MODE",),
                )
            )
        else:
            option_lineage.append(
                OptionGateReasonLineage(
                    identifier=candidate.identifier,
                    candidate_fingerprint=candidate_fp,
                    evaluated=True,
                    eligible=evaluation.eligible,
                    reason_codes=evaluation.reason_codes,
                )
            )

    lineage = DecisionReasonLineage(
        stock_economics_reason_codes=stock_economics.reason_codes,
        stock_gate_evaluated=stock_gate_evaluated,
        stock_gate_eligible=stock_gate_eligible,
        stock_gate_reason_codes=stock_gate_reasons,
        option_gate_lineage=tuple(option_lineage),
        selection_reason_codes=decision.reason_codes,
    )

    return SimulationDecisionRecord(
        contract_version=SIMULATION_DECISION_RECORD_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
        decision_created_utc=decision_created_utc,
        forecast_contract_fingerprint=MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
        forecast_fingerprint=forecast_fingerprint(forecast),
        stock_economics_contract_fingerprint=STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
        trade_expression_contract_fingerprint=TRADE_EXPRESSION_CONTRACT_FINGERPRINT,
        actionability_policy_fingerprint=actionability_policy_fingerprint(
            actionability_policy
        ),
        trade_expression_mode=mode,
        forecast=forecast,
        stock_inputs=stock_inputs,
        stock_economics=stock_economics,
        actionability_policy=actionability_policy,
        option_candidates=normalized_options,
        option_candidate_fingerprints=option_fingerprints,
        trade_expression_decision=decision,
        reason_lineage=lineage,
    )
