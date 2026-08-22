from __future__ import annotations

from dataclasses import dataclass

from packages.ai.case_builder import ReviewPromptPacket, build_review_case_packet
from packages.ai.provider import AIProviderResponse, AIReviewProvider
from packages.ai.structured_output import review_json_schema, validate_review_payload
from packages.schemas.ai_review import AIReviewPayload
from packages.schemas.case_file import Phase13CaseFile
from packages.schemas.deep_research import DeepResearchCase


@dataclass(frozen=True, slots=True)
class CompletedAIReview:
    prompt: ReviewPromptPacket
    provider_response: AIProviderResponse
    review: AIReviewPayload


class IndependentAIAnalyst:
    def __init__(self, provider: AIReviewProvider) -> None:
        self.provider = provider

    def review_case(
        self,
        case: Phase13CaseFile,
        research: DeepResearchCase,
    ) -> CompletedAIReview:
        packet = build_review_case_packet(case, research)
        schema = review_json_schema(packet.evidence_paths)
        response = self.provider.review(packet, json_schema=schema)
        review = validate_review_payload(
            response.parsed_payload,
            allowed_evidence_paths=packet.evidence_paths,
        )
        return CompletedAIReview(
            prompt=packet,
            provider_response=response,
            review=review,
        )
