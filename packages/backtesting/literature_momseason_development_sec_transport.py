from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import SECEDGARClient
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
)

from .literature_momseason_development_progress import (
    MomSeasonDevelopmentResearchWithProgress,
)


LIT01_SEC_IDENTITY_TRANSPORT_REPAIR_VERSION = (
    "lit01-sec-identity-transport-v2-scientific-bound-windows-safe-cache"
)
LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES = (
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
)
LIT01_SEC_IDENTITY_CACHE_KEY_HEX_CHARS = 20


def _sec_identity_cache_key(instrument_id: str, endpoint_session: date) -> str:
    """Return a compact deterministic storage key for validated SEC evidence.

    The key is storage-only. Instrument ID, endpoint, CIK, aliases, source hashes,
    and the evidence fingerprint remain inside the payload and are revalidated on
    every cache hit by the identity layer. A key collision therefore fails closed
    as a payload identity mismatch rather than silently reusing evidence.
    """

    material = f"{instrument_id}\x00{endpoint_session.isoformat()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:LIT01_SEC_IDENTITY_CACHE_KEY_HEX_CHARS]


class MomSeasonDevelopmentResearchWithProgressScientificSEC(
    MomSeasonDevelopmentResearchWithProgress
):
    """LIT-01 runner with bounded SEC transport and Windows-safe evidence storage.

    This remains a transport/persistence-only wrapper. It preserves the global/default
    SEC complete-submission ceiling and opts only this isolated pre-outcome identity-
    continuity client into ATLAS's already-approved scientific submission ceiling.
    It also shortens only the isolated SEC evidence cache path so atomic temporary
    filenames remain well below legacy Windows path limits on the target machine.
    """

    def sec_identity_evidence_path(self, instrument_id: str, endpoint_session: date) -> Path:
        key = _sec_identity_cache_key(instrument_id, endpoint_session)
        return self.root / "si" / f"{key}.json"

    def _ensure_sec_clients(self) -> tuple[SECEDGARClient, SECEDGARArchiveClient]:
        try:
            if self._sec_submissions_client is None:
                self._sec_submissions_client = SECEDGARClient()
            if self._sec_archive_client is None:
                self._sec_archive_client = SECEDGARArchiveClient(
                    submission_max_response_bytes=(
                        LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES
                    )
                )
            elif (
                self._sec_archive_client.submission_max_response_bytes
                != LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES
            ):
                raise ProviderError(
                    "LIT-01 SEC identity archive client was initialized with an "
                    "unexpected submission response bound"
                )
        except ProviderError as exc:
            raise RuntimeError(
                "official SEC identity-continuity source could not initialize under "
                "the bounded ATLAS scientific archive configuration"
            ) from exc
        return self._sec_submissions_client, self._sec_archive_client

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        print(
            "[LIT-01][SEC-TRANSPORT] isolated identity submission ceiling"
            f"={LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES} bytes"
            " | compact Windows-safe SEC evidence cache enabled"
            " | global/default SEC ceiling unchanged",
            flush=True,
        )
        return super().run(
            acquire=acquire,
            force_plan=force_plan,
            force_acquire=force_acquire,
        )
