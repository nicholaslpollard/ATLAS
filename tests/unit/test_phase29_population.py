from __future__ import annotations

from typing import Type

import pandas as pd
import pytest

import packages.backtesting.phase29_population as phase29_population
from packages.backtesting.phase29_policy import PHASE29_PCA_MIN_PEERS, PHASE29_REQUIRED_CLOSES
from packages.backtesting.phase29_population import Phase29PopulationBuilder, Phase29PopulationError
from packages.backtesting.phase29_relative_value import Phase29RelativeValueError


def _population_fixture() -> tuple[pd.DataFrame, tuple[pd.Timestamp, ...], pd.DataFrame]:
    sessions = tuple(pd.date_range("2026-01-02", periods=PHASE29_REQUIRED_CLOSES, freq="B"))
    observation_date = sessions[-1].date()
    source = pd.DataFrame({"as_of_date": [observation_date]})
    records: list[dict[str, object]] = []
    for peer_index in range(PHASE29_PCA_MIN_PEERS):
        for session_index, session in enumerate(sessions):
            records.append(
                {
                    "observation_date": observation_date,
                    "peer_instrument_id": f"i-{peer_index}",
                    "history_date": session.date(),
                    "close": 100.0 + peer_index + 0.15 * session_index + 0.001 * session_index**2,
                }
            )
    return source, sessions, pd.DataFrame.from_records(records)


def _builder_with_history(monkeypatch: pytest.MonkeyPatch) -> tuple[Phase29PopulationBuilder, pd.DataFrame]:
    source, sessions, history = _population_fixture()
    observation_date = sessions[-1].date()
    expected = tuple(session.date() for session in sessions)
    builder = object.__new__(Phase29PopulationBuilder)
    monkeypatch.setattr(
        builder,
        "_history_rows",
        lambda _source, *, splits: (
            history,
            {observation_date: expected},
            {observation_date: PHASE29_PCA_MIN_PEERS},
            {observation_date: PHASE29_PCA_MIN_PEERS},
        ),
    )
    return builder, source


def test_phase29_population_censors_only_expected_relative_value_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder, source = _builder_with_history(monkeypatch)

    def expected_failure(*_args: object, **_kwargs: object) -> object:
        raise Phase29RelativeValueError("expected unusable PCA session")

    monkeypatch.setattr(phase29_population, "pca_residual_dislocations", expected_failure)

    with pytest.raises(Phase29PopulationError, match="produced zero rows"):
        builder._relative_value_frame(source, splits=pd.DataFrame(), development=False)


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_phase29_population_does_not_mask_programming_failures(
    monkeypatch: pytest.MonkeyPatch,
    error_type: Type[Exception],
) -> None:
    builder, source = _builder_with_history(monkeypatch)

    def programming_failure(*_args: object, **_kwargs: object) -> object:
        raise error_type("programming defect")

    monkeypatch.setattr(phase29_population, "pca_residual_dislocations", programming_failure)

    with pytest.raises(error_type, match="programming defect"):
        builder._relative_value_frame(source, splits=pd.DataFrame(), development=False)
