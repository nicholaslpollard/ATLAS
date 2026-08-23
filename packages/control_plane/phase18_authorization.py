from __future__ import annotations

from dataclasses import dataclass

from packages.control_plane.phase18_policy import (
    PHASE18_CONFIRMATION_TEXT,
    PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT,
    PHASE18_REQUIRED_BROKERS,
)


class Phase18AuthorizationError(ValueError):
    pass


@dataclass(frozen=True)
class Phase18MutationAuthorization:
    broker: str
    authorize_provider_mutation: bool = False
    confirmation_text: str = ""
    authorize_destructive_cleanup: bool = False

    def validate(self) -> None:
        broker = self.broker.strip().lower()
        if broker not in PHASE18_REQUIRED_BROKERS:
            raise Phase18AuthorizationError(
                f"Phase 18 broker must be one of {PHASE18_REQUIRED_BROKERS}"
            )
        if PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED:
            raise Phase18AuthorizationError("Phase 18 live execution must remain disabled")
        if PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT:
            raise Phase18AuthorizationError(
                "Phase 18 provider mutation must never be enabled by default"
            )
        if not self.authorize_provider_mutation:
            raise Phase18AuthorizationError(
                "real paper-provider mutation requires explicit per-run authorization"
            )
        if self.confirmation_text != PHASE18_CONFIRMATION_TEXT:
            raise Phase18AuthorizationError(
                "paper-provider mutation confirmation text is missing or incorrect"
            )

    @property
    def normalized_broker(self) -> str:
        return self.broker.strip().lower()


def require_phase18_mutation_authorization(
    authorization: Phase18MutationAuthorization | None,
) -> Phase18MutationAuthorization:
    if authorization is None:
        raise Phase18AuthorizationError(
            "no Phase 18 mutation authorization object was supplied"
        )
    authorization.validate()
    return authorization
