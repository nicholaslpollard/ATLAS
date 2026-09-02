from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from .literature_momseason_development_identity_repair import (
    MomSeasonDevelopmentResearchIdentitySafe,
)


LIT01_DEVELOPMENT_PROGRESS_VERSION = "lit01-development-live-progress-v1"


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0.0:
        return "unknown"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _progress_text(
    *,
    stage: str,
    completed: int,
    total: int,
    started_at: float,
    detail: str = "",
) -> str:
    elapsed = max(0.0, time.monotonic() - started_at)
    percent = 100.0 if total <= 0 else min(100.0, 100.0 * completed / total)
    eta: float | None = None
    if total > 0 and completed > 0 and completed < total:
        eta = (elapsed / completed) * (total - completed)
    suffix = f" | {detail}" if detail else ""
    return (
        f"[LIT-01][{stage}] {completed}/{total} ({percent:5.1f}%)"
        f" | elapsed {_format_duration(elapsed)} | ETA~ {_format_duration(eta)}{suffix}"
    )


def _emit(message: str) -> None:
    print(message, flush=True)


class _ProgressFormationSequence(Sequence[Any]):
    def __init__(self, items: Sequence[Any], *, stage: str) -> None:
        self._items = tuple(items)
        self._stage = stage
        self._started_at = time.monotonic()

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int | slice) -> Any:
        return self._items[index]

    def __iter__(self) -> Iterator[Any]:
        total = len(self._items)
        for index, item in enumerate(self._items, start=1):
            month_start = getattr(item, "month_start", None)
            month_text = month_start.strftime("%Y-%m") if month_start is not None else str(index)
            completed = index - 1
            _emit(
                _progress_text(
                    stage=self._stage,
                    completed=completed,
                    total=total,
                    started_at=self._started_at,
                    detail=f"starting month {index}/{total}: {month_text}",
                )
            )
            yield item
        _emit(
            _progress_text(
                stage=self._stage,
                completed=total,
                total=total,
                started_at=self._started_at,
                detail="month loop complete",
            )
        )


class MomSeasonDevelopmentResearchWithProgress(MomSeasonDevelopmentResearchIdentitySafe):
    """Identity-safe LIT-01 development runner with live console progress only.

    This wrapper does not change the frozen research contract, holdings, source rules,
    or inference. It adds flushed console output around long-running planning,
    continuity-source, target-acquisition, materialization, and evaluation stages.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._overall_started_at = time.monotonic()

    def build_plan(self, *, force: bool = False) -> dict[str, object]:
        started = time.monotonic()
        cached = (
            self.holdings_path().is_file()
            and self.target_plan_path().is_file()
            and self.plan_report_path().is_file()
            and not force
        )
        _emit(
            "[LIT-01][PLAN] starting frozen holdings/target-plan construction"
            + (" (validating cached plan)" if cached else " across 56 development months")
        )
        original = self.development_formations
        if not cached:
            self.development_formations = _ProgressFormationSequence(original, stage="PLAN")  # type: ignore[assignment]
        try:
            report = super().build_plan(force=force)
        finally:
            self.development_formations = original
        _emit(
            f"[LIT-01][PLAN] complete | elapsed {_format_duration(time.monotonic() - started)}"
            f" | holdings={report.get('holdings_rows')} targets={report.get('target_plan_rows')}"
            f" | cached={bool(report.get('skipped'))}"
        )
        return report

    def _load_or_acquire_identity_events(
        self,
        *,
        endpoint_session,
        instrument_id: str,
        rows: list[dict[str, object]],
    ):
        path = self.identity_evidence_path(instrument_id)
        new_provider_read = not path.is_file() and self._allow_identity_source_acquisition
        started = time.monotonic()
        if new_provider_read:
            _emit(
                "[LIT-01][IDENTITY:Massive] source call starting"
                f" | endpoint={endpoint_session} instrument={instrument_id}"
            )
        result = super()._load_or_acquire_identity_events(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
            rows=rows,
        )
        if new_provider_read:
            _emit(
                "[LIT-01][IDENTITY:Massive] source call complete"
                f" | elapsed {_format_duration(time.monotonic() - started)}"
                f" | events={0 if result is None else len(result)}"
            )
        return result

    def _sec_get_json(self, url: str):
        new_provider_read = url not in self._sec_urls_requested_this_run
        started = time.monotonic()
        if new_provider_read:
            _emit(f"[LIT-01][IDENTITY:SEC] submissions request starting | {url}")
        result = super()._sec_get_json(url)
        if new_provider_read:
            _emit(
                "[LIT-01][IDENTITY:SEC] submissions request complete"
                f" | elapsed {_format_duration(time.monotonic() - started)}"
            )
        return result

    def _sec_get_submission(self, filename: str):
        started = time.monotonic()
        _emit(f"[LIT-01][IDENTITY:SEC] 8-K filing request starting | {filename}")
        result = super()._sec_get_submission(filename)
        _emit(
            "[LIT-01][IDENTITY:SEC] 8-K filing request complete"
            f" | elapsed {_format_duration(time.monotonic() - started)}"
        )
        return result

    def _load_or_acquire_sec_identity_ticker(
        self,
        *,
        endpoint_session,
        instrument_id: str,
        rows: list[dict[str, object]],
    ):
        path = self.sec_identity_evidence_path(instrument_id, endpoint_session)
        new_search = not path.is_file() and self._allow_identity_source_acquisition
        started = time.monotonic()
        if new_search:
            aliases = sorted(
                {
                    str(row.get("ticker") or "").strip()
                    for row in rows
                    if str(row.get("ticker") or "").strip()
                }
            )
            _emit(
                "[LIT-01][IDENTITY:SEC] bounded ticker-continuity search starting"
                f" | endpoint={endpoint_session} instrument={instrument_id} aliases={aliases}"
            )
        result = super()._load_or_acquire_sec_identity_ticker(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
            rows=rows,
        )
        if new_search:
            _emit(
                "[LIT-01][IDENTITY:SEC] bounded ticker-continuity search complete"
                f" | elapsed {_format_duration(time.monotonic() - started)}"
                f" | resolved={result}"
            )
        return result

    def acquire_targets(self, *, force: bool = False) -> dict[str, object]:
        self._require_freeze()
        units = self.build_units()
        total = len(units)
        started = time.monotonic()
        availability: Counter[str] = Counter()
        executed = 0
        skipped = 0
        calls = 0
        _emit(
            f"[LIT-01][TARGETS] starting Alpaca development acquisition | units={total}"
        )
        for index, unit in enumerate(units, start=1):
            manifest = None if force else self._load_completed_manifest(unit)
            if manifest is None:
                _emit(
                    _progress_text(
                        stage="TARGETS",
                        completed=index - 1,
                        total=total,
                        started_at=started,
                        detail=(
                            f"starting unit {index}/{total}: endpoint={unit.endpoint_session} "
                            f"batch={unit.batch_index} symbols={len(unit.symbols)}"
                        ),
                    )
                )
                unit_started = time.monotonic()
                manifest = self._acquire_unit(unit)
                executed += 1
                unit_calls = int(manifest.get("provider_calls_performed") or 0)
                calls += unit_calls
                detail = (
                    f"completed endpoint={unit.endpoint_session} batch={unit.batch_index} "
                    f"unit_time={_format_duration(time.monotonic() - unit_started)} calls={unit_calls}"
                )
            else:
                skipped += 1
                detail = f"cached endpoint={unit.endpoint_session} batch={unit.batch_index}"
            for row in manifest.get("symbol_results") or []:
                if isinstance(row, Mapping):
                    availability[str(row.get("availability_status") or "UNKNOWN")] += 1
            _emit(
                _progress_text(
                    stage="TARGETS",
                    completed=index,
                    total=total,
                    started_at=started,
                    detail=detail,
                )
            )
        _emit(
            f"[LIT-01][TARGETS] acquisition complete | elapsed {_format_duration(time.monotonic() - started)}"
            f" | executed={executed} cached={skipped} provider_calls={calls}"
        )
        return {
            "planned_units": total,
            "executed_units_this_run": executed,
            "skipped_units_this_run": skipped,
            "provider_calls_performed_this_run": calls,
            "availability_counts": dict(sorted(availability.items())),
        }

    def _materialize_target_endpoints(self):
        started = time.monotonic()
        _emit("[LIT-01][MATERIALIZE] assembling frozen target endpoint table")
        result = super()._materialize_target_endpoints()
        _emit(
            f"[LIT-01][MATERIALIZE] complete | elapsed {_format_duration(time.monotonic() - started)}"
            f" | availability={dict(sorted(result[1].items()))} | missing_units={result[2]}"
        )
        return result

    def _evaluate(self, endpoint_map):
        started = time.monotonic()
        _emit(
            "[LIT-01][EVALUATE] starting frozen development evaluation"
            " | 2 hypotheses | 56 monthly units each | 2,000 bootstrap replicates"
        )
        result = super()._evaluate(endpoint_map)
        _emit(
            f"[LIT-01][EVALUATE] complete | elapsed {_format_duration(time.monotonic() - started)}"
            f" | source_complete={result.get('source_complete')}"
            f" | complete_returns={result.get('complete_holding_returns')}"
            f" | unavailable_returns={result.get('unavailable_holding_returns')}"
        )
        return result

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        self._overall_started_at = time.monotonic()
        _emit(
            "[LIT-01][RUN] started"
            f" | progress_contract={LIT01_DEVELOPMENT_PROGRESS_VERSION}"
            f" | acquire={acquire} force_plan={force_plan} force_acquire={force_acquire}"
        )
        try:
            result = super().run(
                acquire=acquire,
                force_plan=force_plan,
                force_acquire=force_acquire,
            )
        except Exception as exc:
            _emit(
                f"[LIT-01][RUN] STOPPED | elapsed {_format_duration(time.monotonic() - self._overall_started_at)}"
                f" | {type(exc).__name__}: {exc}"
            )
            raise
        _emit(
            f"[LIT-01][RUN] finished | elapsed {_format_duration(time.monotonic() - self._overall_started_at)}"
            f" | status={result.get('status')}"
        )
        return result
