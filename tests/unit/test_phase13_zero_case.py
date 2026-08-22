from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.portfolio.phase13_engine import PHASE13_NO_CASE_DISPOSITION, Phase13CaseEngine


@dataclass(frozen=True)
class _ZeroInput:
    as_of_date: date = date(2026, 8, 14)
    source_fingerprint: str = "f" * 64
    case_count: int = 0

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": "test",
            "source_fingerprint": self.source_fingerprint,
            "as_of_date": self.as_of_date.isoformat(),
            "case_count": 0,
            "case_instrument_ids": [],
            "research_case_sha256": [],
        }


class _Resolver:
    def resolve(self, as_of_date: date | None = None) -> _ZeroInput:
        result = _ZeroInput()
        assert as_of_date is None or as_of_date == result.as_of_date
        return result


def test_zero_case_engine_never_initializes_provider_or_reads_portfolio(tmp_path) -> None:
    engine = object.__new__(Phase13CaseEngine)
    engine.settings = None
    engine.input_resolver = _Resolver()
    engine.root = tmp_path

    manifest = engine.run(as_of_date=date(2026, 8, 14))
    assert manifest["phase12_case_count"] == 0
    assert manifest["case_file_count"] == 0
    assert manifest["no_case_disposition"] == PHASE13_NO_CASE_DISPOSITION
    assert manifest["provider_initialized"] is False
    assert manifest["news_provider_calls"] == 0
    assert manifest["option_chain_provider_calls"] == 0
    assert manifest["portfolio_snapshot_reads"] == 0
    assert manifest["production_ml_writes"] == 0
    assert manifest["broker_writes"] == 0
    assert manifest["order_writes"] == 0
    assert manifest["execution_present"] is False
