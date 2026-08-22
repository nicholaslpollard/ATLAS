from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from packages.ai.analyst import IndependentAIAnalyst
from packages.ai.case_builder import build_review_case_packet
from packages.ai.openai_provider import OpenAIResponsesReviewProvider, _extract_output_text
from packages.ai.phase14_policy import (
    PHASE14_AI_CAN_CHANGE_GEOMETRY,
    PHASE14_AI_CAN_CREATE_ORDER,
    PHASE14_DEFAULT_MODEL,
    PHASE14_EXTERNAL_DELIVERY_ENABLED,
    PHASE14_MODEL_TOOLS_ENABLED,
    PHASE14_REVIEW_DISPOSITIONS,
    phase14_policy_fingerprint,
)
from packages.ai.provider import AIProviderResponse, AIReviewProvider
from packages.ai.structured_output import AIReviewOutputError, review_json_schema, validate_review_payload
from packages.alerts.builder import build_alert_artifact
from packages.schemas.ai_review import (
    AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
    AIReviewPayload,
    AIReviewRecord,
)
from packages.schemas.case_file import (
    EvidenceAvailability,
    GeometryStatus,
    InstrumentKind,
    InstrumentSelection,
    NewsContextSummary,
    Phase13CaseFile,
    PortfolioRiskAssessment,
    PortfolioRiskStatus,
    TradeGeometry,
)
from packages.schemas.deep_research import (
    AnalogueDistribution,
    AnalogueQuality,
    DeepResearchCase,
    EmpiricalPathScenarios,
    ScenarioQuantiles,
)
from packages.schemas.discovery_score import DiscoveryDirection


def _q(scale: float = 1.0) -> ScenarioQuantiles:
    return ScenarioQuantiles(
        p05=-0.05 * scale,
        p10=-0.03 * scale,
        p25=-0.01 * scale,
        median=0.01 * scale,
        p75=0.06 * scale,
        p90=0.09 * scale,
        p95=0.12 * scale,
        mean=0.02 * scale,
    )


def _research() -> DeepResearchCase:
    return DeepResearchCase(
        instrument_id="figi-1",
        ticker="XYZ",
        as_of_date=date(2026, 8, 14),
        direction=DiscoveryDirection.BULLISH,
        market_state="BULL",
        ticker_state="UPTREND",
        phase11_candidate_sha256="b" * 64,
        research_source_fingerprint="c" * 64,
        similarity_feature_names=("return_1", "natr_14"),
        current_feature_values={"return_1": 0.02, "natr_14": 0.04},
        eligible_pool_rows=1000,
        analogue_distribution=AnalogueDistribution(
            rows=100,
            unique_instruments=50,
            weighted_mean_return=0.025,
            mean_return=0.02,
            median_return=0.015,
            positive_rate=0.61,
            stddev_return=0.08,
            p10_return=-0.05,
            p75_return=0.07,
            worst_return=-0.20,
            best_return=0.30,
        ),
        analogue_quality=AnalogueQuality(
            status="ROBUST",
            analogue_count=100,
            unique_instruments=50,
            first_session_date=date(2022, 1, 3),
            last_session_date=date(2026, 4, 30),
            mean_distance=0.5,
            median_distance=0.45,
            p90_distance=0.8,
            path_rows=100,
            path_coverage=1.0,
            reason_codes=("ROBUST_ANALOGUE_EVIDENCE",),
        ),
        scenarios=EmpiricalPathScenarios(
            available=True,
            draw_count=1000,
            seed=1401,
            source_path_rows=100,
            session_1=_q(0.5),
            session_2=_q(0.75),
            session_3=_q(1.0),
            max_adverse_excursion=_q(1.0),
            max_favorable_excursion=_q(1.2),
            terminal_positive_rate=0.61,
            reason_codes=("EMPIRICAL_PATH_SCENARIOS_AVAILABLE",),
        ),
        analogue_artifact_path="/tmp/analogue.parquet",
        analogue_artifact_sha256="d" * 64,
        path_artifact_path="/tmp/path.parquet",
        path_artifact_sha256="e" * 64,
        research_complete=True,
        reason_codes=("PHASE12_RESEARCH_COMPLETE",),
    )


def _case() -> Phase13CaseFile:
    return Phase13CaseFile(
        instrument_id="figi-1",
        ticker="XYZ",
        as_of_date=date(2026, 8, 14),
        direction=DiscoveryDirection.BULLISH,
        phase12_case_sha256="a" * 64,
        phase12_research_complete=True,
        market_state="BULL",
        ticker_state="UPTREND",
        news_context=NewsContextSummary(
            availability=EvidenceAvailability.AVAILABLE,
            cutoff_utc=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
            lookback_calendar_days=7,
            article_count=3,
            positive_count=2,
            neutral_count=1,
            negative_count=0,
            sentiment_score=0.5,
            latest_published_utc=datetime(2026, 8, 14, 18, 0, tzinfo=UTC),
            reason_codes=("POINT_IN_TIME_NEWS_CONTEXT",),
        ),
        instrument_selection=InstrumentSelection(
            primary_kind=InstrumentKind.EQUITY,
            primary_ticker="XYZ",
            option_chain_availability=EvidenceAvailability.UNAVAILABLE,
            reason_codes=("EQUITY_PRIMARY",),
        ),
        geometry=TradeGeometry(
            status=GeometryStatus.AVAILABLE,
            direction=DiscoveryDirection.BULLISH,
            horizon_sessions=3,
            reference_entry=100.0,
            stop=95.0,
            target=110.0,
            risk_fraction=0.05,
            reward_fraction=0.10,
            reward_to_risk=2.0,
            natr_14=0.04,
            empirical_mae_p10=-0.03,
            empirical_mfe_p75=0.10,
            reference_only_not_fill=True,
            reason_codes=("EVIDENCE_BOUNDED_GEOMETRY",),
        ),
        portfolio_risk=PortfolioRiskAssessment(
            status=PortfolioRiskStatus.ADMISSIBLE,
            proposed_risk_budget=500.0,
            proposed_quantity=10,
            proposed_notional=1000.0,
            projected_single_name_fraction=0.01,
            projected_gross_fraction=0.20,
            max_abs_correlation=0.30,
            open_positions_before=2,
            proposed_quantity_is_order=False,
            reason_codes=("PORTFOLIO_RISK_ADMISSIBLE",),
        ),
        phase14_review_ready=True,
        reason_codes=("PHASE14_REVIEW_READY",),
    )


class _FakeProvider(AIReviewProvider):
    @property
    def provider_name(self) -> str:
        return "FAKE"

    @property
    def model_name(self) -> str:
        return "fake-reviewer-v1"

    def review(self, packet, *, json_schema):  # type: ignore[override]
        assert json_schema["properties"]["disposition"]["enum"] == list(PHASE14_REVIEW_DISPOSITIONS)
        payload = {
            "contract_version": AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
            "disposition": "CAUTIOUS",
            "summary": "The case is coherent, but analogue downside remains material.",
            "reasons": [
                {
                    "text": "The deterministic reward-to-risk geometry is positive.",
                    "evidence_paths": ["phase13.geometry.reward_to_risk"],
                }
            ],
            "risk_flags": [
                {
                    "text": "The analogue distribution includes a negative lower tail.",
                    "evidence_paths": ["phase12.analogue_distribution.p10_return"],
                }
            ],
            "disagreements": [],
        }
        return AIProviderResponse(
            provider=self.provider_name,
            model=self.model_name,
            response_id="fake-1",
            parsed_payload=payload,
            raw_response={"id": "fake-1", "output": []},
        )


def test_phase14_policy_is_nonauthoritative_and_artifact_only() -> None:
    assert PHASE14_REVIEW_DISPOSITIONS == ("APPROVE", "CAUTIOUS", "REJECT")
    assert PHASE14_AI_CAN_CHANGE_GEOMETRY is False
    assert PHASE14_AI_CAN_CREATE_ORDER is False
    assert PHASE14_MODEL_TOOLS_ENABLED is False
    assert PHASE14_EXTERNAL_DELIVERY_ENABLED is False
    assert PHASE14_DEFAULT_MODEL == "gpt-5.6-terra"
    assert len(phase14_policy_fingerprint()) == 64


def test_review_payload_forbids_trade_plan_fields() -> None:
    with pytest.raises(ValidationError):
        AIReviewPayload.model_validate(
            {
                "contract_version": AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
                "disposition": "REJECT",
                "summary": "Risk is too high.",
                "reasons": [{"text": "Tail risk.", "evidence_paths": ["phase12.x"]}],
                "risk_flags": [],
                "disagreements": [],
                "stop": 95.0,
            }
        )


def test_prompt_packet_is_sanitized_and_has_exact_grounding_paths() -> None:
    packet = build_review_case_packet(_case(), _research())
    assert "/tmp/" not in packet.input_text
    assert "analogue_artifact_sha256" not in packet.input_text
    assert "phase13.geometry.reward_to_risk" in packet.evidence_paths
    assert "phase12.analogue_distribution.p10_return" in packet.evidence_paths
    assert len(packet.fingerprint) == 64


def test_structured_schema_enumerates_only_allowed_evidence_paths() -> None:
    packet = build_review_case_packet(_case(), _research())
    schema = review_json_schema(packet.evidence_paths)
    evidence_enum = schema["properties"]["reasons"]["items"]["properties"]["evidence_paths"]["items"]["enum"]
    assert "phase13.geometry.reward_to_risk" in evidence_enum
    assert "phase13.geometry.not_a_field" not in evidence_enum
    assert schema["additionalProperties"] is False


def test_unknown_grounding_path_is_rejected_even_if_payload_shape_is_valid() -> None:
    with pytest.raises(AIReviewOutputError):
        validate_review_payload(
            {
                "contract_version": AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
                "disposition": "CAUTIOUS",
                "summary": "Caution.",
                "reasons": [{"text": "Unknown claim.", "evidence_paths": ["phase13.fake"]}],
                "risk_flags": [],
                "disagreements": [],
            },
            allowed_evidence_paths=("phase13.geometry.reward_to_risk",),
        )


def test_approve_cannot_carry_deterministic_disagreement() -> None:
    with pytest.raises(AIReviewOutputError):
        validate_review_payload(
            {
                "contract_version": AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
                "disposition": "APPROVE",
                "summary": "Approve but disagree.",
                "reasons": [
                    {"text": "Geometry is valid.", "evidence_paths": ["phase13.geometry.reward_to_risk"]}
                ],
                "risk_flags": [],
                "disagreements": [
                    {"text": "I disagree.", "evidence_paths": ["phase13.geometry.reward_to_risk"]}
                ],
            },
            allowed_evidence_paths=("phase13.geometry.reward_to_risk",),
        )


def test_independent_analyst_uses_provider_but_revalidates_output() -> None:
    result = IndependentAIAnalyst(_FakeProvider()).review_case(_case(), _research())
    assert result.review.disposition.value == "CAUTIOUS"
    assert result.provider_response.provider == "FAKE"
    assert result.review.reasons[0].evidence_paths == ("phase13.geometry.reward_to_risk",)


def test_openai_request_body_has_no_tools_and_uses_strict_structured_output() -> None:
    packet = build_review_case_packet(_case(), _research())
    schema = review_json_schema(packet.evidence_paths)
    provider = OpenAIResponsesReviewProvider(api_key="test-key", model="gpt-5.6-terra")
    body = provider._request_body(packet, json_schema=schema)
    assert body["store"] is False
    assert "tools" not in body
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"] == schema


def test_openai_output_text_extraction_rejects_refusal() -> None:
    assert _extract_output_text(
        {"output": [{"content": [{"type": "output_text", "text": "{\"ok\":true}"}]}]}
    ) == '{"ok":true}'
    with pytest.raises(Exception):
        _extract_output_text({"output": [{"content": [{"type": "refusal", "refusal": "no"}]}]})


def test_alert_artifact_preserves_engine_vs_ai_without_delivery_or_execution() -> None:
    case = _case()
    result = IndependentAIAnalyst(_FakeProvider()).review_case(case, _research())
    review_record = AIReviewRecord(
        instrument_id=case.instrument_id,
        ticker=case.ticker,
        as_of_date=case.as_of_date,
        phase13_case_sha256="f" * 64,
        phase13_case_contract_version=case.contract_version,
        prompt_contract_version=result.prompt.contract_version,
        prompt_fingerprint=result.prompt.fingerprint,
        provider=result.provider_response.provider,
        model=result.provider_response.model,
        response_id=result.provider_response.response_id,
        reviewed_at_utc=datetime.now(UTC),
        review=result.review,
    )
    alert = build_alert_artifact(
        case,
        phase13_case_sha256="f" * 64,
        review_record=review_record,
        ai_review_sha256="1" * 64,
    )
    assert alert.disposition.value == "CAUTIOUS"
    assert alert.external_delivery_enabled is False
    assert alert.delivered is False
    assert alert.execution_present is False
    assert "Engine:" in alert.engine_summary
    assert "not fills or orders" in alert.engine_summary
