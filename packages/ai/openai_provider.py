from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from packages.ai.case_builder import ReviewPromptPacket
from packages.ai.phase14_policy import (
    PHASE14_DEFAULT_MODEL,
    PHASE14_DEFAULT_PROVIDER,
    PHASE14_OPENAI_ENDPOINT,
    PHASE14_OPENAI_MAX_OUTPUT_TOKENS,
    PHASE14_OPENAI_TIMEOUT_SECONDS,
)
from packages.ai.provider import AIProviderResponse, AIReviewProvider
from packages.core.secrets import get_secret


class OpenAIReviewProviderError(RuntimeError):
    pass


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    output = payload.get("output")
    if not isinstance(output, list):
        raise OpenAIReviewProviderError("OpenAI response contains no output array")
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise OpenAIReviewProviderError("OpenAI reviewer refused the structured audit request")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                text_parts.append(str(part["text"]))
    text = "".join(text_parts).strip()
    if not text:
        raise OpenAIReviewProviderError("OpenAI response contains no structured output text")
    return text


class OpenAIResponsesReviewProvider(AIReviewProvider):
    """Minimal stdlib adapter for the OpenAI Responses API.

    The adapter intentionally exposes no tools and sends only the sanitized immutable
    case packet. API credentials remain process-environment secrets.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str = PHASE14_OPENAI_ENDPOINT,
        timeout_seconds: int = PHASE14_OPENAI_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or get_secret("OPENAI_API_KEY")
        self._model = (model or os.getenv("ATLAS_PHASE14_OPENAI_MODEL") or PHASE14_DEFAULT_MODEL).strip()
        if not self._model:
            raise OpenAIReviewProviderError("Phase 14 OpenAI model cannot be blank")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return PHASE14_DEFAULT_PROVIDER

    @property
    def model_name(self) -> str:
        return self._model

    def _request_body(
        self,
        packet: ReviewPromptPacket,
        *,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "instructions": packet.instructions,
            "input": packet.input_text,
            "max_output_tokens": PHASE14_OPENAI_MAX_OUTPUT_TOKENS,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "atlas_phase14_review",
                    "schema": json_schema,
                    "strict": True,
                }
            },
        }

    def review(
        self,
        packet: ReviewPromptPacket,
        *,
        json_schema: dict[str, Any],
    ) -> AIProviderResponse:
        body = self._request_body(packet, json_schema=json_schema)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
            except Exception:  # pragma: no cover - defensive response-body handling
                detail = ""
            raise OpenAIReviewProviderError(
                f"OpenAI Responses API HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OpenAIReviewProviderError(f"OpenAI Responses API request failed: {type(exc).__name__}") from exc
        if not isinstance(raw, dict):
            raise OpenAIReviewProviderError("OpenAI Responses API returned a non-object payload")
        output_text = _extract_output_text(raw)
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise OpenAIReviewProviderError("OpenAI structured output was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise OpenAIReviewProviderError("OpenAI structured output must be a JSON object")
        response_id = raw.get("id")
        return AIProviderResponse(
            provider=self.provider_name,
            model=self.model_name,
            response_id=str(response_id) if response_id is not None else None,
            parsed_payload=parsed,
            raw_response=raw,
        )
