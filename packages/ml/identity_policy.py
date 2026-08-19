from __future__ import annotations

from collections.abc import Iterable

from packages.ml.identity_probe import AUTHORITATIVE_INTERVAL, UNIQUE_REFERENCE_NO_REUSE


ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION = (
    "ml-historical-identity-policy-v1-authoritative-or-unique-no-reuse-structural"
)

HISTORICAL_IDENTITY_SAFE_STATUSES = (
    AUTHORITATIVE_INTERVAL,
    UNIQUE_REFERENCE_NO_REUSE,
)

CURRENT_ROUTE_FILTER_USED = False
CURRENT_ACTIVE_FILTER_USED = False
CURRENT_DELISTED_FILTER_USED = False
TICKER_TEXT_SPLICING_ALLOWED = False


def historical_identity_safe(status: str) -> bool:
    return str(status) in HISTORICAL_IDENTITY_SAFE_STATUSES


def historical_observation_eligible(
    *,
    identity_status: str,
    structural_exclusion_reasons: Iterable[str] = (),
) -> bool:
    """Return whether a historical observation enters the Phase 10 ML population.

    Historical eligibility is intentionally observation-driven. Current routing,
    current active/delisted state, and ticker-text continuity are not inputs. A row
    must have either one date-bounded authoritative ticker interval or one unique,
    unreused strong/medium reference identity, then pass the lifetime-structural
    market/locale/exchange/security-type gate measured in Gate 2.
    """

    return historical_identity_safe(identity_status) and not any(
        str(reason).strip() for reason in structural_exclusion_reasons
    )
