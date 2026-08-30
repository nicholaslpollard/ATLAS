from __future__ import annotations

import hashlib
import json

from packages.backtesting.alpha_gate_beneficial_ownership_development import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
)
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND,
    SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS,
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
    SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
)


BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_CONTRACT = (
    "alpha-gate-beneficial-ownership-development-transport-repair-v1-"
    "bounded-large-sec-submissions-pre-outcome"
)
BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT = (
    "a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb"
)
BENEFICIAL_OWNERSHIP_FAILED_TRANSPORT_PROGRESS = "3500_of_5200_predictor_walk_pre_reconstruction_zero_outcomes"


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def beneficial_ownership_development_transport_repair_fingerprint() -> str:
    payload = {
        "scientific_fingerprint": BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        "development_implementation_fingerprint": (
            BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
        ),
        "default_submission_limit_bytes": SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
        "scientific_submission_limit_bytes": (
            SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
        ),
        "max_calls_per_second": SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND,
        "min_call_interval_seconds": SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS,
        "scope": "scientific_acquisition_only_no_selection_or_outcome_change",
        "failed_run_boundary": BENEFICIAL_OWNERSHIP_FAILED_TRANSPORT_PROGRESS,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
