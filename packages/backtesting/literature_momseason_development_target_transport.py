from __future__ import annotations

from collections import defaultdict
from datetime import date

from .literature_momseason_development import (
    TargetAcquisitionUnit,
    _chunks,
    _target_unit_id,
)
from .literature_momseason_development_sec_transport import (
    MomSeasonDevelopmentResearchWithProgressScientificSEC,
)


LIT01_DEVELOPMENT_TARGET_TRANSPORT_CONTRACT = (
    "lit01-development-target-transport-v1-dedup-endpoint-ticker-preserve-instrument-rows"
)


class MomSeasonDevelopmentResearchTargetTransportSafe(
    MomSeasonDevelopmentResearchWithProgressScientificSEC
):
    """Share one provider observation across frozen rows with the same date/ticker.

    The frozen target plan remains keyed by ``(endpoint_session, instrument_id)`` and
    is not rewritten or merged.  Alpaca, however, is queried by ticker.  When more
    than one already-resolved frozen instrument row requires the same ticker on the
    same endpoint, one ``(endpoint_session, ticker)`` market observation is sufficient
    transport-wise.  Downstream materialization independently maps that source result
    back to every frozen instrument row.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._target_transport_shared_groups: list[dict[str, object]] = []
        self._target_transport_extra_instrument_rows = 0
        self._target_transport_reported = False

    def build_units(self) -> list[TargetAcquisitionUnit]:
        rows, report = self._load_target_plan()
        fingerprint = str(report["target_plan_fingerprint"])
        by_session: dict[date, set[str]] = defaultdict(set)
        instruments_by_source_key: dict[tuple[date, str], set[str]] = defaultdict(set)

        for row in rows:
            endpoint = date.fromisoformat(str(row["endpoint_session"]))
            if endpoint not in self.allowed_target_sessions:
                raise RuntimeError("LIT-01 development acquisition escaped target whitelist")
            ticker = str(row["historical_ticker"])
            instrument_id = str(row["instrument_id"])
            if not ticker:
                raise RuntimeError(
                    "LIT-01 development target plan contains an empty historical ticker: "
                    f"{endpoint} {instrument_id}"
                )
            by_session[endpoint].add(ticker)
            instruments_by_source_key[(endpoint, ticker)].add(instrument_id)

        shared_groups: list[dict[str, object]] = []
        extra_rows = 0
        for (endpoint, ticker), instrument_ids in sorted(
            instruments_by_source_key.items(),
            key=lambda item: (item[0][0], item[0][1]),
        ):
            if len(instrument_ids) <= 1:
                continue
            ordered_ids = sorted(instrument_ids)
            shared_groups.append(
                {
                    "endpoint_session": endpoint.isoformat(),
                    "historical_ticker": ticker,
                    "instrument_ids": ordered_ids,
                    "instrument_count": len(ordered_ids),
                }
            )
            extra_rows += len(ordered_ids) - 1

        self._target_transport_shared_groups = shared_groups
        self._target_transport_extra_instrument_rows = extra_rows
        if shared_groups and not getattr(self, "_target_transport_reported", False):
            print(
                "[LIT-01][TARGET-TRANSPORT] shared endpoint/ticker source observations"
                f" | groups={len(shared_groups)} | extra frozen instrument rows={extra_rows}"
                " | frozen instrument identities remain separate",
                flush=True,
            )
            for item in shared_groups[:8]:
                print(
                    "[LIT-01][TARGET-TRANSPORT] shared source observation"
                    f" | endpoint={item['endpoint_session']}"
                    f" ticker={item['historical_ticker']}"
                    f" instruments={item['instrument_ids']}",
                    flush=True,
                )
            if len(shared_groups) > 8:
                print(
                    "[LIT-01][TARGET-TRANSPORT] additional shared source groups omitted"
                    f" | remaining={len(shared_groups) - 8}",
                    flush=True,
                )
            self._target_transport_reported = True

        units: list[TargetAcquisitionUnit] = []
        batch_size = int(self.alpaca.cfg.symbol_batch_size)
        for endpoint in sorted(by_session):
            symbols = sorted(by_session[endpoint])
            for batch_index, batch in enumerate(_chunks(symbols, batch_size)):
                units.append(
                    TargetAcquisitionUnit(
                        endpoint_session=endpoint,
                        batch_index=batch_index,
                        symbols=batch,
                        plan_fingerprint=fingerprint,
                        unit_id=_target_unit_id(
                            endpoint_session=endpoint,
                            batch_index=batch_index,
                            symbols=batch,
                            plan_fingerprint=fingerprint,
                        ),
                    )
                )
        return units

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        result = super().run(
            acquire=acquire,
            force_plan=force_plan,
            force_acquire=force_acquire,
        )
        shared_groups = list(getattr(self, "_target_transport_shared_groups", []))
        result["target_transport"] = {
            "contract_version": LIT01_DEVELOPMENT_TARGET_TRANSPORT_CONTRACT,
            "source_key": "endpoint_session + historical_ticker",
            "frozen_plan_key": "endpoint_session + instrument_id",
            "shared_source_groups": len(shared_groups),
            "extra_frozen_instrument_rows_sharing_source": int(
                getattr(self, "_target_transport_extra_instrument_rows", 0)
            ),
            "shared_group_details": shared_groups,
            "frozen_instrument_rows_merged": False,
            "target_plan_rewritten": False,
        }
        return result
