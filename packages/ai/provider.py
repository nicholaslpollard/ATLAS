from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from packages.ai.case_builder import ReviewPromptPacket


@dataclass(frozen=True, slots=True)
class AIProviderResponse:
    provider: str
    model: str
    response_id: str | None
    parsed_payload: dict[str, Any]
    raw_response: dict[str, Any]


class AIReviewProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def review(
        self,
        packet: ReviewPromptPacket,
        *,
        json_schema: dict[str, Any],
    ) -> AIProviderResponse:
        raise NotImplementedError
