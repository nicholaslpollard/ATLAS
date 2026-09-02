from __future__ import annotations

from packages.backtesting import literature_momseason_development_sec_transport as transport
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
    SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
)


def test_lit01_sec_transport_uses_explicit_scientific_bound(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSubmissionsClient:
        pass

    class FakeArchiveClient:
        def __init__(self, *, submission_max_response_bytes: int) -> None:
            captured["limit"] = submission_max_response_bytes
            self.submission_max_response_bytes = submission_max_response_bytes

    monkeypatch.setattr(transport, "SECEDGARClient", FakeSubmissionsClient)
    monkeypatch.setattr(transport, "SECEDGARArchiveClient", FakeArchiveClient)

    runner = object.__new__(transport.MomSeasonDevelopmentResearchWithProgressScientificSEC)
    runner._sec_submissions_client = None
    runner._sec_archive_client = None

    submissions, archive = runner._ensure_sec_clients()

    assert isinstance(submissions, FakeSubmissionsClient)
    assert isinstance(archive, FakeArchiveClient)
    assert captured["limit"] == SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
    assert archive.submission_max_response_bytes == 256_000_000


def test_lit01_scientific_bound_does_not_change_global_default() -> None:
    assert transport.LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES == 256_000_000
    assert SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES == 256_000_000
    assert SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES == 20_000_000
    assert (
        transport.LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES
        > SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES
    )
