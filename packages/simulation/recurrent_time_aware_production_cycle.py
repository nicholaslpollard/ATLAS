from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.execution.current_webull_time_aware_stock_close import (
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT,
    CurrentWebullTimeAwareStockCloseBundleV1,
    apply_current_webull_time_aware_stock_close_bundle_v1,
)
from packages.simulation.recurrent_cycle import (
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
)
from packages.simulation.recurrent_production_cycle import (
    RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
    RecurrentProductionCycleError,
    RecurrentProductionCycleV1,
)
from packages.simulation.recurrent_time_aware_production_cycle_contract import (
    RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT,
    RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_VERSION = str(
    RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT["contract_id"]
)


class RecurrentTimeAwareProductionCycleError(
    RecurrentProductionCycleError
):
    pass


@dataclass
class RecurrentTimeAwareProductionCycleV1(
    RecurrentProductionCycleV1
):
    """Time-aware CLOSE extension that preserves accepted production v1."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
            != "c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca"
        ):
            raise RecurrentTimeAwareProductionCycleError(
                "base production-cycle contract fingerprint mismatch"
            )
        if (
            CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
            != "7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45"
        ):
            raise RecurrentTimeAwareProductionCycleError(
                "time-aware CLOSE contract fingerprint mismatch"
            )
        if (
            RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
            != "c16ce1d4b9923d857673a92e6a4378a76699d6413ccf3ee8dbed9b138a894e84"
        ):
            raise RecurrentTimeAwareProductionCycleError(
                "time-aware production-cycle contract fingerprint mismatch"
            )

    def apply_close(
        self,
        *,
        bundle: CurrentWebullTimeAwareStockCloseBundleV1,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        if (
            bundle.contract_fingerprint
            != CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeAwareProductionCycleError(
                "time-aware production CLOSE bundle contract fingerprint mismatch"
            )
        if (
            bundle.cycle_id != self.identity.cycle_id
            or bundle.cycle_fingerprint
            != self.identity.cycle_fingerprint
        ):
            raise RecurrentTimeAwareProductionCycleError(
                "time-aware production CLOSE bundle is bound to a different cycle"
            )
        if not self._stage_recorded(RecurrentCycleStage.CLOSE):
            current_state = self.runner.runtime.current_account().state
            if (
                bundle.source_recurrent_state_fingerprint
                != current_state.state_fingerprint
            ):
                raise RecurrentTimeAwareProductionCycleError(
                    "time-aware production CLOSE bundle is stale for current recurrent state"
                )
        return apply_current_webull_time_aware_stock_close_bundle_v1(
            runner=self.runner,
            identity=self.identity,
            bundle=bundle,
            now_utc=now_utc,
        )


__all__ = [
    "RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT",
    "RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_VERSION",
    "RecurrentTimeAwareProductionCycleError",
    "RecurrentTimeAwareProductionCycleV1",
]
