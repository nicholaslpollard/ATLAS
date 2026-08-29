from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.backtesting.phase32_predictor_acquisition as acquisition
from packages.backtesting.phase32_policy import PHASE32_CANDIDATES
from packages.backtesting.phase32_predictor_acquisition import (
    Phase32PredictorAcquisitionError,
    Phase32PredictorSourceAcquisition,
    _decision_and_exit_sessions,
)
from scripts.run_phase32_predictor_acquisition import _Phase32SemanticAcquisitionAdapter


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(provider="data/provider", derived="data/derived")
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = tuple(rows)


ACCESSION = "0000000001-21-000001"
DISCLOSURE = {
    "accession_number": ACCESSION,
    "cik": "0000000001",
    "filing_date": "2021-08-16",
    "primary_category": "capital_and_financing",
    "secondary_category": "shareholder_returns",
    "tertiary_category": "share_repurchase_program",
    "supporting_text": "Issuer authorized a share repurchase program.",
    "tickers": ["ABC"],
}
INDEX = {
    "accession_number": ACCESSION,
    "cik": "1",
    "filing_date": "2021-08-16",
    "form_type": "8-K",
    "filing_url": "https://www.sec.gov/Archives/example",
    "ticker": "ABC",
}
TEXT = {
    "accession_number": ACCESSION,
    "cik": "0000000001",
    "filing_date": "2021-08-16",
    "form_type": "8-K",
    "filing_url": "https://www.sec.gov/Archives/example",
    "items_text": "Item 8.01. Issuer authorized a share repurchase program.",
    "ticker": "ABC",
}
TAXONOMY_ROWS = tuple(
    {
        "taxonomy": "1.0",
        "primary_category": primary,
        "secondary_category": secondary,
        "tertiary_category": tertiary,
        "description": f"Frozen Phase32 fixture taxonomy row for {tertiary}.",
    }
    for candidate in PHASE32_CANDIDATES
    for primary, secondary, tertiary in candidate.taxonomy_triples
)
REFERENCE = {
    "ticker": "ABC",
    "name": "ABC Corp",
    "market": "stocks",
    "locale": "us",
    "currency_name": "usd",
    "primary_exchange": "XNYS",
    "type": "CS",
    "active": True,
    "composite_figi": "BBG000000001",
    "share_class_figi": "BBG001000001",
    "cik": "0000000001",
}


def _taxonomy_sha() -> str:
    raw = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in TAXONOMY_ROWS
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FakeIndexClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def eight_k_window(self, *, start_date: date, end_date: date) -> Result:
        self.calls += 1
        if self.fail:
            raise AssertionError("network index call should have been satisfied from cache")
        return Result([INDEX] if start_date.month == 8 and start_date.year == 2021 else [])


class FakeSemanticClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.taxonomy_calls = 0
        self.disclosure_calls = 0
        self.text_calls = 0
        self.fail = fail

    def taxonomy(self) -> Result:
        self.taxonomy_calls += 1
        if self.fail:
            raise AssertionError("network taxonomy call should have been satisfied from cache")
        return Result(list(TAXONOMY_ROWS))

    def eight_k_disclosures(self, *, start_date: date, end_date: date) -> Result:
        self.disclosure_calls += 1
        if self.fail:
            raise AssertionError("network disclosure call should have been satisfied from cache")
        return Result([DISCLOSURE] if start_date.month == 8 and start_date.year == 2021 else [])

    def eight_k_text(self, *, cik: object, filing_date: date) -> tuple[dict[str, object], ...]:
        self.text_calls += 1
        if self.fail:
            raise AssertionError("network text call should have been satisfied from cache")
        assert str(cik) == "0000000001"
        assert filing_date == date(2021, 8, 16)
        return (TEXT,)


class AcceptedSemanticClientStub:
    def __init__(self) -> None:
        self.taxonomy_calls = 0
        self.disclosure_calls = 0
        self.text_calls = 0

    def taxonomy(self) -> Result:
        self.taxonomy_calls += 1
        return Result(list(TAXONOMY_ROWS))

    def disclosures_window(self, *, start_date: date, end_date: date) -> Result:
        self.disclosure_calls += 1
        assert start_date == date(2021, 8, 16)
        assert end_date == date(2021, 8, 31)
        return Result([DISCLOSURE])

    def eight_k_text(self, *, cik: object, filing_date: date) -> tuple[dict[str, object], ...]:
        self.text_calls += 1
        return (TEXT,)


class FakeSECClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def filing_metadata(self, *, cik: object, accession_number: str, filing_date: str) -> dict[str, object]:
        self.calls += 1
        if self.fail:
            raise AssertionError("SEC call should have been satisfied from cache")
        return {
            "accession_number": ACCESSION,
            "issuer_cik": "0000000001",
            "filing_date": "2021-08-16",
            "acceptance_datetime": "2021-08-16T08:00:00-04:00",
            "form": "8-K",
            "item_codes": ["8.01"],
            "primary_document": "abc.htm",
            "source_url": "https://data.sec.gov/submissions/CIK0000000001.json",
            "source_record_json": "{}\n",
            "source_record_sha256": "a" * 64,
        }


class FakeReferenceProvider:
    def __init__(self, *, fail: bool = False, ambiguous: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.ambiguous = ambiguous

    def ticker_overview(self, ticker: str, as_of_date: date) -> dict[str, object]:
        self.calls += 1
        if self.fail:
            raise AssertionError("reference call should have been satisfied from cache")
        row = dict(REFERENCE)
        row["ticker"] = ticker
        if self.ambiguous and ticker == "XYZ":
            row["composite_figi"] = "BBG000000999"
        return row


def _patch_range_and_taxonomy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acquisition, "PHASE32_ACQUISITION_START", date(2021, 8, 16))
    monkeypatch.setattr(acquisition, "PHASE32_ACQUISITION_END", date(2021, 8, 31))
    monkeypatch.setattr(acquisition, "PHASE32_ACCEPTED_TAXONOMY_SHA256", _taxonomy_sha())


def test_production_semantic_adapter_binds_accepted_provider_interface() -> None:
    accepted = AcceptedSemanticClientStub()
    adapter = _Phase32SemanticAcquisitionAdapter(accepted)  # type: ignore[arg-type]

    assert adapter.taxonomy().rows == TAXONOMY_ROWS
    assert adapter.eight_k_disclosures(
        start_date=date(2021, 8, 16), end_date=date(2021, 8, 31)
    ).rows == (DISCLOSURE,)
    assert adapter.eight_k_text(cik="0000000001", filing_date=date(2021, 8, 16)) == (TEXT,)
    assert accepted.taxonomy_calls == 1
    assert accepted.disclosure_calls == 1
    assert accepted.text_calls == 1


def test_acceptance_time_uses_first_regular_open_strictly_after_acceptance() -> None:
    decision, exit_session = _decision_and_exit_sessions("2021-08-16T08:00:00-04:00")
    assert decision == date(2021, 8, 16)
    assert exit_session == date(2021, 8, 23)

    after_open, after_open_exit = _decision_and_exit_sessions("2021-08-16T10:00:00-04:00")
    assert after_open == date(2021, 8, 17)
    assert after_open_exit == date(2021, 8, 24)


def test_source_acquisition_builds_predictor_without_market_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_range_and_taxonomy(monkeypatch)
    settings = FakeSettings(tmp_path)
    index = FakeIndexClient()
    semantic = FakeSemanticClient()
    sec = FakeSECClient()
    reference = FakeReferenceProvider()

    report = Phase32PredictorSourceAcquisition(
        settings, index, semantic, sec, reference
    ).run()

    assert report["pass"] is True
    assert report["frozen_candidate_source_accessions"] == 1
    assert report["eligible_predictor_rows"] == 1
    assert report["candidate_predictor_counts"] == {"share_repurchase_long": 1}
    assert report["stage_predictor_counts"] == {"development": 1}
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["stock_price_rows_read"] == 0
    assert report["spy_price_rows_read"] == 0
    assert report["options_rows_read"] == 0
    assert index.calls == 1
    assert semantic.taxonomy_calls == 1
    assert semantic.disclosure_calls == 1
    assert semantic.text_calls == 1
    assert sec.calls == 1
    assert reference.calls == 2

    predictor_path = Path(report["predictor_path"])
    predictor = json.loads(predictor_path.read_text(encoding="utf-8").strip())
    assert predictor["candidate_id"] == "share_repurchase_long"
    assert predictor["direction"] == "LONG"
    assert predictor["decision_session"] == "2021-08-16"
    assert predictor["exit_session"] == "2021-08-23"
    assert predictor["identity_quality"] == "strong"
    assert predictor["outcome_rows_read"] == 0


def test_joint_filer_index_rows_are_preserved_but_do_not_contaminate_issuer_tickers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_range_and_taxonomy(monkeypatch)
    co_filer = dict(INDEX)
    co_filer["cik"] = "0000000002"
    co_filer["ticker"] = "XYZ"

    class JointFilerIndexClient(FakeIndexClient):
        def eight_k_window(self, *, start_date: date, end_date: date) -> Result:
            self.calls += 1
            if start_date.month == 8 and start_date.year == 2021:
                return Result([INDEX, co_filer])
            return Result([])

    reference = FakeReferenceProvider()
    settings = FakeSettings(tmp_path)
    report = Phase32PredictorSourceAcquisition(
        settings,
        JointFilerIndexClient(),
        FakeSemanticClient(),
        FakeSECClient(),
        reference,
    ).run()

    assert report["eligible_predictor_rows"] == 1
    assert reference.calls == 2
    evidence_path = (
        tmp_path
        / "data/provider/phase32_sec_8k_predictor_acquisition/v1/candidate_accession_records.jsonl"
    )
    record = json.loads(evidence_path.read_text(encoding="utf-8").strip())
    assert record["index_row_count"] == 2
    assert record["issuer_index_row_count"] == 1
    assert record["co_filer_index_row_count"] == 1
    assert record["index_filer_ciks"] == ["0000000001", "0000000002"]
    assert record["co_filer_index_ciks"] == ["0000000002"]
    assert record["provider_tickers"] == ["ABC"]


def test_joint_filer_reconciliation_fails_closed_when_disclosure_cik_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_range_and_taxonomy(monkeypatch)
    co_filer_only = dict(INDEX)
    co_filer_only["cik"] = "0000000002"
    co_filer_only["ticker"] = "XYZ"

    class CoFilerOnlyIndexClient(FakeIndexClient):
        def eight_k_window(self, *, start_date: date, end_date: date) -> Result:
            self.calls += 1
            if start_date.month == 8 and start_date.year == 2021:
                return Result([co_filer_only])
            return Result([])

    with pytest.raises(
        Phase32PredictorAcquisitionError,
        match="no original-8-K index row for disclosure CIK",
    ):
        Phase32PredictorSourceAcquisition(
            FakeSettings(tmp_path),
            CoFilerOnlyIndexClient(),
            FakeSemanticClient(),
            FakeSECClient(),
            FakeReferenceProvider(),
        ).run()


def test_source_acquisition_is_resumable_from_atomic_local_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_range_and_taxonomy(monkeypatch)
    settings = FakeSettings(tmp_path)
    Phase32PredictorSourceAcquisition(
        settings,
        FakeIndexClient(),
        FakeSemanticClient(),
        FakeSECClient(),
        FakeReferenceProvider(),
    ).run()

    report = Phase32PredictorSourceAcquisition(
        settings,
        FakeIndexClient(fail=True),
        FakeSemanticClient(fail=True),
        FakeSECClient(fail=True),
        FakeReferenceProvider(fail=True),
    ).run()
    assert report["eligible_predictor_rows"] == 1
    assert report["network_reads"] == {}
    assert report["cache_hits"]["taxonomy"] == 1
    assert report["cache_hits"]["massive_index"] == 1
    assert report["cache_hits"]["massive_disclosures"] == 1
    assert report["cache_hits"]["massive_text"] == 1
    assert report["cache_hits"]["sec_submissions"] == 1
    assert report["cache_hits"]["massive_reference"] == 2


def test_multiple_pit_instruments_are_excluded_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_range_and_taxonomy(monkeypatch)
    monkeypatch.setattr(
        acquisition,
        "_candidate_taxonomy_map",
        lambda: {
            (
                "capital_and_financing",
                "shareholder_returns",
                "share_repurchase_program",
            ): ("share_repurchase_long", "LONG")
        },
    )
    disclosure = dict(DISCLOSURE)
    disclosure["tickers"] = ["ABC", "XYZ"]

    class AmbiguousSemantic(FakeSemanticClient):
        def eight_k_disclosures(self, *, start_date: date, end_date: date) -> Result:
            self.disclosure_calls += 1
            return Result([disclosure])

    report = Phase32PredictorSourceAcquisition(
        FakeSettings(tmp_path),
        FakeIndexClient(),
        AmbiguousSemantic(),
        FakeSECClient(),
        FakeReferenceProvider(ambiguous=True),
    ).run()
    assert report["eligible_predictor_rows"] == 0
    assert report["exclusion_counts"] == {"AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS": 1}
