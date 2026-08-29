from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase32_semantic_source_census import (
    PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT,
    Phase32SemanticSourceCensusError,
    build_phase32_semantic_v2_source_census,
)


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(provider="data/provider", derived="data/derived")
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def _sha_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path) -> FakeSettings:
    settings = FakeSettings(root)
    provider = root / "data/provider/phase32_sec_8k_semantic_feasibility/v2"
    derived = root / "data/derived/strategy_evaluation/phase32/semantic_v2"
    (provider / "massive_disclosures").mkdir(parents=True, exist_ok=True)
    derived.mkdir(parents=True, exist_ok=True)

    taxonomy_rows = [
        {
            "taxonomy": "1.0",
            "primary_category": "capital_and_financing",
            "secondary_category": "equity_activity",
            "tertiary_category": "share_repurchase",
            "description": "Issuer repurchases shares.",
        },
        {
            "taxonomy": "1.0",
            "primary_category": "capital_and_financing",
            "secondary_category": "equity_activity",
            "tertiary_category": "equity_issuance",
            "description": "Issuer sells equity.",
        },
    ]
    taxonomy_text = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in taxonomy_rows
    )
    taxonomy_path = provider / "taxonomy.jsonl"
    taxonomy_path.write_text(taxonomy_text, encoding="utf-8")

    disclosure_rows = [
        {
            "accession_number": "0000000001-26-000001",
            "cik": "0000000001",
            "primary_category": "capital_and_financing",
            "secondary_category": "equity_activity",
            "tertiary_category": "share_repurchase",
            "tickers": ["ABC"],
        },
        {
            "accession_number": "0000000002-26-000001",
            "cik": "0000000002",
            "primary_category": "capital_and_financing",
            "secondary_category": "equity_activity",
            "tertiary_category": "equity_issuance",
            "tickers": [],
        },
    ]
    disclosure_text = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in disclosure_rows
    )
    disclosure_path = provider / "massive_disclosures/research_boundary.jsonl"
    disclosure_path.write_text(disclosure_text, encoding="utf-8")

    source_report = {
        "phase32_semantic_v2_fingerprint": PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT,
        "pass": True,
        "taxonomy_sha256": _sha_path(taxonomy_path),
        "taxonomy_versions": ["1.0"],
        "total_disclosure_rows": 2,
        "target_outcome_rows_read": 0,
        "protected_candidate_rows_read": 0,
        "protected_return_rows_read": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
        "automation_writes": 0,
        "windows": [
            {
                "label": "research_boundary",
                "disclosure_rows": 2,
                "disclosure_sha256": _sha_path(disclosure_path),
            }
        ],
    }
    (derived / "phase32_8k_semantic_feasibility_v2.json").write_text(
        json.dumps(source_report), encoding="utf-8"
    )
    return settings  # type: ignore[return-value]


def test_source_census_is_local_source_only_and_counts_taxonomy(tmp_path: Path) -> None:
    census = build_phase32_semantic_v2_source_census(_write_fixture(tmp_path))
    assert census["total_disclosure_rows"] == 2
    assert census["taxonomy_rows"] == 2
    assert census["observed_taxonomy_rows"] == 2
    assert census["unique_accessions"] == 2
    assert census["ticker_mapped_rows"] == 1
    assert census["ticker_unmapped_rows"] == 1
    assert census["target_outcome_rows_read"] == 0
    assert census["protected_return_rows_read"] == 0
    assert census["network_calls"] == 0


def test_source_census_fails_on_immutable_disclosure_drift(tmp_path: Path) -> None:
    settings = _write_fixture(tmp_path)
    path = (
        tmp_path
        / "data/provider/phase32_sec_8k_semantic_feasibility/v2/massive_disclosures/research_boundary.jsonl"
    )
    path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(Phase32SemanticSourceCensusError, match="hash drifted"):
        build_phase32_semantic_v2_source_census(settings)
