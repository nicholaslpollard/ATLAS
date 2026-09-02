from __future__ import annotations

import hashlib
from http.client import IncompleteRead

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import SEC_EDGAR_MAX_ATTEMPTS
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    sec_archive_submission_url,
)


class _Response:
    def __init__(self, payload: bytes, *, incomplete: bool = False) -> None:
        self.payload = payload
        self.incomplete = incomplete
        self.headers: dict[str, str] = {}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, _amount: int) -> bytes:
        if self.incomplete:
            partial = self.payload[: max(1, len(self.payload) // 2)]
            raise IncompleteRead(partial=partial, expected=len(self.payload) - len(partial))
        return self.payload


def _submission_url() -> str:
    return sec_archive_submission_url("edgar/data/1234567/0001234567-26-000001.txt")


def test_incomplete_read_retries_from_zero_and_never_accepts_partial_body() -> None:
    partial_attempt_payload = b"PARTIAL-BODY-MUST-NOT-BE-ACCEPTED"
    complete_payload = b"COMPLETE-SEC-SUBMISSION"
    responses = [
        _Response(partial_attempt_payload, incomplete=True),
        _Response(complete_payload),
    ]
    calls: list[str] = []

    def opener(request, *, timeout: float):
        del timeout
        calls.append(request.full_url)
        return responses.pop(0)

    client = SECEDGARArchiveClient(opener=opener, sleeper=lambda _seconds: None)
    document = client.get_text(_submission_url())

    assert len(calls) == 2
    assert calls[0] == calls[1] == _submission_url()
    assert document.text == complete_payload.decode("utf-8")
    assert document.source_sha256 == hashlib.sha256(complete_payload).hexdigest()
    assert "PARTIAL-BODY" not in document.text

    # The successful complete response is cached; the truncated attempt never was.
    again = client.get_text(_submission_url())
    assert again == document
    assert len(calls) == 2


def test_incomplete_read_exhaustion_stays_bounded_and_fails_closed() -> None:
    calls = 0

    def opener(request, *, timeout: float):
        nonlocal calls
        del request, timeout
        calls += 1
        return _Response(b"STILL-TRUNCATED", incomplete=True)

    client = SECEDGARArchiveClient(opener=opener, sleeper=lambda _seconds: None)

    with pytest.raises(ProviderError, match="IncompleteRead"):
        client.get_text(_submission_url())

    assert calls == SEC_EDGAR_MAX_ATTEMPTS
