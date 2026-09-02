from __future__ import annotations

from datetime import date
from pathlib import Path

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


def test_sec_identity_cache_key_is_compact_deterministic_and_endpoint_specific() -> None:
    first = transport._sec_identity_cache_key(
        "ins_8baf6f337bd90aade5b27626", date(2025, 4, 30)
    )
    again = transport._sec_identity_cache_key(
        "ins_8baf6f337bd90aade5b27626", date(2025, 4, 30)
    )
    other_date = transport._sec_identity_cache_key(
        "ins_8baf6f337bd90aade5b27626", date(2025, 5, 30)
    )
    other_instrument = transport._sec_identity_cache_key("ins_other", date(2025, 4, 30))

    assert first == again
    assert len(first) == transport.LIT01_SEC_IDENTITY_CACHE_KEY_HEX_CHARS == 20
    assert set(first) <= set("0123456789abcdef")
    assert first != other_date
    assert first != other_instrument


def test_sec_identity_evidence_path_has_large_windows_atomic_write_headroom() -> None:
    runner = object.__new__(transport.MomSeasonDevelopmentResearchWithProgressScientificSEC)
    # This reproduces the target-machine development-root depth without depending on
    # whether the CI worker itself is Windows. The cache's relative suffix is what the
    # transport wrapper controls and must keep compact for atomic temporary filenames.
    runner.root = Path("development_root")

    path = runner.sec_identity_evidence_path(
        "ins_8baf6f337bd90aade5b27626", date(2025, 4, 30)
    )
    relative = path.relative_to(runner.root)

    assert relative.parts[0] == "si"
    assert len(relative.name) == 25  # 20 hex chars + '.json'
    assert "ins_8baf6f337bd90aade5b27626" not in str(relative)
    assert "2025-04-30" not in str(relative)
    assert len(str(relative)) <= 30
