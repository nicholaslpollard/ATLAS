from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.providers.massive.reference_data import MassiveReferenceProvider


REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION = (
    "regime-classification-probe-v1-massive-sic-point-in-time"
)


@dataclass(frozen=True, slots=True)
class ClassificationCandidate:
    instrument_id: str
    ticker: str
    security_type: str | None


@dataclass(frozen=True, slots=True)
class ClassificationObservation:
    instrument_id: str
    ticker: str
    security_type: str | None
    status: str
    provider_ticker: str | None
    exact_ticker_match: bool
    sic_code: str | None
    sic_description: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class RegimeClassificationProbeReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    population_count: int
    requested_sample_size: int
    sampled_count: int
    successful_response_count: int
    exact_ticker_match_count: int
    sic_code_count: int
    sic_description_count: int
    missing_sic_count: int
    provider_error_count: int
    sic_coverage_fraction: float
    source_sha256: dict[str, str]
    by_security_type: dict[str, dict[str, int]]
    top_sic_descriptions: list[dict[str, object]]
    missing_sic_examples: list[dict[str, object]]
    provider_error_examples: list[dict[str, object]]
    observations: list[ClassificationObservation]
    report_path: str


class RegimeClassificationProbe:
    """Measure real point-in-time SIC coverage before a sector mapping is designed.

    This is an evidence probe, not a permanent classification registry. It samples
    the exact Phase 8 discovery population deterministically and asks Massive's
    point-in-time Ticker Overview endpoint for raw SIC facts. No SIC-to-sector,
    GICS, ETF, or strategy-routing mapping is inferred here.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        provider: MassiveReferenceProvider | None = None,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.provider = provider or MassiveReferenceProvider(settings)

    @staticmethod
    def _sample_key(candidate: ClassificationCandidate) -> str:
        payload = f"{candidate.instrument_id}\0{candidate.ticker}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def deterministic_sample(
        cls,
        candidates: Iterable[ClassificationCandidate],
        sample_size: int,
    ) -> list[ClassificationCandidate]:
        if sample_size <= 0:
            raise ValueError("sample_size must be greater than zero")
        ordered = sorted(
            candidates,
            key=lambda item: (cls._sample_key(item), item.instrument_id, item.ticker),
        )
        return ordered[: min(sample_size, len(ordered))]

    @staticmethod
    def coverage_fraction(sic_count: int, successful_count: int) -> float:
        return 0.0 if successful_count <= 0 else float(sic_count) / float(successful_count)

    def _load_population(self, as_of_date: date) -> tuple[list[ClassificationCandidate], dict[str, str]]:
        state_path = self.paths.discovery_state_file(as_of_date)
        universe_path = self.paths.universe_snapshot_file(as_of_date)
        missing = [str(path) for path in (state_path, universe_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Phase 9 classification probe inputs are missing:\n  " + "\n  ".join(missing)
            )

        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT
                    s.instrument_id,
                    s.ticker,
                    u.security_type
                FROM read_parquet({sql_string(state_path)}) AS s
                LEFT JOIN read_parquet({sql_string(universe_path)}) AS u
                  ON u.instrument_id = s.instrument_id
                 AND u.ticker = s.ticker
                ORDER BY s.instrument_id, s.ticker
                """
            ).fetchall()
        finally:
            con.close()

        candidates = [
            ClassificationCandidate(
                instrument_id=str(instrument_id),
                ticker=str(ticker),
                security_type=None if security_type is None else str(security_type),
            )
            for instrument_id, ticker, security_type in rows
        ]
        if not candidates:
            raise ValueError(f"Discovery state contains no classification candidates for {as_of_date}")

        source_sha256 = {
            "discovery_state": sha256_file(state_path),
            "universe": sha256_file(universe_path),
        }
        return candidates, source_sha256

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _observe(
        self,
        candidate: ClassificationCandidate,
        as_of_date: date,
    ) -> ClassificationObservation:
        try:
            raw = self.provider.ticker_overview(candidate.ticker, as_of_date)
        except ProviderError as exc:
            return ClassificationObservation(
                instrument_id=candidate.instrument_id,
                ticker=candidate.ticker,
                security_type=candidate.security_type,
                status="provider_error",
                provider_ticker=None,
                exact_ticker_match=False,
                sic_code=None,
                sic_description=None,
                error=f"{type(exc).__name__}: {exc}",
            )

        provider_ticker = self._text(raw.get("ticker"))
        return ClassificationObservation(
            instrument_id=candidate.instrument_id,
            ticker=candidate.ticker,
            security_type=candidate.security_type,
            status="ok",
            provider_ticker=provider_ticker,
            exact_ticker_match=provider_ticker == candidate.ticker,
            sic_code=self._text(raw.get("sic_code")),
            sic_description=self._text(raw.get("sic_description")),
            error=None,
        )

    @staticmethod
    def _security_type_summary(
        observations: Iterable[ClassificationObservation],
    ) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "sampled": 0,
                "successful": 0,
                "sic_code": 0,
                "missing_sic": 0,
                "provider_error": 0,
            }
        )
        for item in observations:
            key = item.security_type or "<NULL>"
            summary[key]["sampled"] += 1
            if item.status == "ok":
                summary[key]["successful"] += 1
                if item.sic_code:
                    summary[key]["sic_code"] += 1
                else:
                    summary[key]["missing_sic"] += 1
            else:
                summary[key]["provider_error"] += 1
        return {key: dict(value) for key, value in sorted(summary.items())}

    def build(
        self,
        as_of_date: date,
        *,
        sample_size: int = 250,
        example_limit: int = 20,
    ) -> RegimeClassificationProbeReport:
        candidates, source_sha256 = self._load_population(as_of_date)
        sampled = self.deterministic_sample(candidates, sample_size)
        observations = [self._observe(candidate, as_of_date) for candidate in sampled]

        successful = [item for item in observations if item.status == "ok"]
        provider_errors = [item for item in observations if item.status == "provider_error"]
        with_sic = [item for item in successful if item.sic_code]
        with_description = [item for item in successful if item.sic_description]
        missing_sic = [item for item in successful if not item.sic_code]

        description_counts = Counter(
            item.sic_description for item in successful if item.sic_description
        )
        top_sic_descriptions = [
            {"sic_description": description, "count": int(count)}
            for description, count in description_counts.most_common(20)
        ]

        target = self.paths.regime_classification_probe_report(as_of_date)
        generated_at = datetime.now(UTC)
        report = RegimeClassificationProbeReport(
            contract_version=REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=generated_at.isoformat(),
            population_count=len(candidates),
            requested_sample_size=int(sample_size),
            sampled_count=len(sampled),
            successful_response_count=len(successful),
            exact_ticker_match_count=sum(item.exact_ticker_match for item in successful),
            sic_code_count=len(with_sic),
            sic_description_count=len(with_description),
            missing_sic_count=len(missing_sic),
            provider_error_count=len(provider_errors),
            sic_coverage_fraction=self.coverage_fraction(len(with_sic), len(successful)),
            source_sha256=source_sha256,
            by_security_type=self._security_type_summary(observations),
            top_sic_descriptions=top_sic_descriptions,
            missing_sic_examples=[asdict(item) for item in missing_sic[:example_limit]],
            provider_error_examples=[asdict(item) for item in provider_errors[:example_limit]],
            observations=observations,
            report_path=str(target),
        )

        payload = asdict(report)
        atomic_write_text(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return report
