from __future__ import annotations

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
    "lit01-sec-identity-transport-v1-explicit-scientific-submission-bound"
)
LIT01_SEC_IDENTITY_SUBMISSION_MAX_RESPONSE_BYTES = (
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
)


class MomSeasonDevelopmentResearchWithProgressScientificSEC(
    MomSeasonDevelopmentResearchWithProgress
):
    """LIT-01 runner with an explicit bounded scientific SEC archive client.

    This is a transport-only wrapper. It preserves the global/default SEC complete-
    submission ceiling and opts only this isolated pre-outcome identity-continuity
    client into ATLAS's already-approved scientific submission ceiling.
    """

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
            " | global/default SEC ceiling unchanged",
            flush=True,
        )
        return super().run(
            acquire=acquire,
            force_plan=force_plan,
            force_acquire=force_acquire,
        )
