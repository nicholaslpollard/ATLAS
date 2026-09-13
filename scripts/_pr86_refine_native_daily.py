from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_source() -> None:
    path = ROOT / "packages/backtesting/successor_spy_benchmark_source.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    B35DevelopmentMinuteSource,\n    _validate_native_plan_record,\n",
        "    B35DevelopmentMinuteSource,\n    _assert_native_path,\n    _validate_native_plan_record,\n",
        "b35 native path import",
    )
    text = replace_once(
        text,
        "from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT\n",
        "from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, UNIT_CONTRACT\n",
        "native unit contract import",
    )
    text = replace_once(
        text,
        "from packages.data.alpaca_v2_postbuild import (\n    RESEARCH_DAILY_CONTRACT,\n    SPLIT_DAILY_CONTRACT,\n    SPLIT_DAILY_UNIT_CONTRACT,\n)\n",
        "from packages.data.alpaca_v2_postbuild import (\n    NATIVE_ACCEPTANCE_CONTRACT,\n    RESEARCH_DAILY_CONTRACT,\n)\n",
        "native acceptance import",
    )
    text = replace_once(
        text,
        '"atlas-successor-spy-benchmark-source-v3-minute-primary-pre2026-split-daily-fallback"',
        '"atlas-successor-spy-benchmark-source-v3-minute-primary-pre2026-native-daily-fallback"',
        "contract name",
    )
    text = replace_once(
        text,
        '"fallback_source": "ALPACA_V2_SPLIT_ADJUSTED_DAILY_LINEAGED_BY_ACCEPTED_RESEARCH_DAILY",',
        '"fallback_source": "ALPACA_V2_NATIVE_CANONICAL_RAW_DAILY_LINEAGED_BY_ACCEPTED_RESEARCH_DAILY_NATIVE_ACCEPTANCE",',
        "fallback source",
    )

    fn_start = text.index("def _daily_fallback_rows(\n")
    fn_end = text.index("def resolve_spy_benchmark_source(\n", fn_start)
    replacement = r'''def _daily_fallback_rows(
    settings: AtlasSettings,
    *,
    requested_sessions: tuple[date, ...],
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not requested_sessions:
        return pd.DataFrame(columns=["session_date", "close"]), {
            "native_acceptance_fingerprint": None,
            "unit_count": 0,
            "unit_bindings": [],
            "protected_or_future_daily_partition_opened": False,
        }
    if any(session.year > SPY_DAILY_FALLBACK_LAST_YEAR for session in requested_sessions):
        raise SuccessorSpyBenchmarkSourceError("native daily fallback requested inside 2026")

    project_root = settings.project_root.resolve()
    layout = V2Layout.beneath((project_root / "data").resolve())
    adapter = ReferenceV2DailyLakeAdapter(settings)
    _research_manifest_path, research_manifest = adapter._manifest(None)
    if research_manifest.get("contract") != RESEARCH_DAILY_CONTRACT:
        raise SuccessorSpyBenchmarkSourceError("accepted research-daily contract drifted")
    expected_native_fingerprint = str(
        research_manifest.get("native_acceptance_fingerprint") or ""
    )
    if len(expected_native_fingerprint) != 64:
        raise SuccessorSpyBenchmarkSourceError(
            "research-daily native acceptance lineage fingerprint is missing"
        )

    native_report_path = (layout.validation / "native_acceptance.json").absolute()
    _assert_native_path(
        native_report_path,
        expected=native_report_path,
        root=layout.root,
        label="native acceptance report",
    )
    native_report = _read_json(native_report_path, "native acceptance report")
    required = {
        "contract": NATIVE_ACCEPTANCE_CONTRACT,
        "status": "PASS",
        "v1_ancestry": "FORBIDDEN",
        "protected_return_rows_read": 0,
        "production_promoted": False,
    }
    for field, expected in required.items():
        if native_report.get(field) != expected:
            raise SuccessorSpyBenchmarkSourceError(
                f"native acceptance report {field} is not {expected!r}"
            )
    if str(native_report.get("acceptance_fingerprint") or "") != expected_native_fingerprint:
        raise SuccessorSpyBenchmarkSourceError(
            "native daily lineage differs from accepted research daily"
        )
    if "SPY" in {str(value) for value in native_report.get("excluded_symbols") or []}:
        raise SuccessorSpyBenchmarkSourceError("SPY is excluded from accepted native V2 source")
    inventory = native_report.get("unit_inventory")
    if not isinstance(inventory, dict):
        raise SuccessorSpyBenchmarkSourceError("native acceptance unit inventory binding is missing")
    inventory_path = Path(str(inventory.get("path") or "")).absolute()
    _assert_native_path(
        inventory_path,
        expected=(layout.validation / "native_unit_inventory.parquet").absolute(),
        root=layout.root,
        label="native unit inventory",
    )
    if not inventory_path.is_file() or _sha256_file(inventory_path) != str(
        inventory.get("sha256") or ""
    ):
        raise SuccessorSpyBenchmarkSourceError("native acceptance unit inventory hash drifted")

    years = {session.year for session in requested_sessions}
    records, plan_report = _load_plan_records_for_fallback(layout, years=years)
    requested = set(requested_sessions)
    pieces: list[pd.DataFrame] = []
    unit_bindings: list[dict[str, object]] = []
    for record in sorted(records, key=lambda item: int(item["year"])):
        year = int(record["year"])
        batch = int(record["batch_index"])
        unit_id = str(record["unit_id"])
        prefix = unit_id[:20]
        partition = Path(f"year={year:04d}") / f"batch={batch:04d}"
        checkpoint_path = (
            layout.checkpoints
            / "native_units"
            / "1d"
            / partition
            / f"{prefix}.json"
        ).absolute()
        canonical_path = (layout.canonical_daily / partition / f"{prefix}.parquet").absolute()
        if year > SPY_DAILY_FALLBACK_LAST_YEAR:
            raise SuccessorSpyBenchmarkSourceError("refusing to open 2026 native daily partition")
        _assert_native_path(
            checkpoint_path,
            expected=checkpoint_path,
            root=layout.root,
            label=f"native SPY daily checkpoint {year}",
        )
        _assert_native_path(
            canonical_path,
            expected=canonical_path,
            root=layout.root,
            label=f"native SPY daily canonical {year}",
        )
        checkpoint = _read_json(checkpoint_path, f"native SPY daily checkpoint {year}")
        if checkpoint.get("contract") != UNIT_CONTRACT:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint contract drifted: {year}"
            )
        if str(checkpoint.get("status") or "") not in {
            "COMPLETE",
            "COMPLETE_WITH_QUARANTINE",
        }:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint is not accepted complete: {year}"
            )
        if (
            checkpoint.get("unit_id") != unit_id
            or checkpoint.get("policy_sha256") != record.get("policy_sha256")
            or checkpoint.get("universe_sha256") != record.get("universe_sha256")
            or canonical_sha256(checkpoint.get("unit")) != canonical_sha256(record)
        ):
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint identity drifted: {year}"
            )
        canonical = checkpoint.get("canonical")
        if not isinstance(canonical, dict):
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical binding missing: {year}"
            )
        recorded_path = Path(str(canonical.get("path") or "")).absolute()
        _assert_native_path(
            recorded_path,
            expected=canonical_path,
            root=layout.root,
            label=f"native SPY daily recorded canonical {year}",
        )
        expected_sha = str(canonical.get("sha256") or "")
        if len(expected_sha) != 64 or not canonical_path.is_file():
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical binding incomplete: {year}"
            )
        if _sha256_file(canonical_path) != expected_sha:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical hash drifted: {year}"
            )
        rejected = {
            str(item.get("symbol") or "")
            for item in checkpoint.get("provider_rejections") or []
            if isinstance(item, dict)
        }
        if "SPY" in rejected:
            raise SuccessorSpyBenchmarkSourceError(
                f"SPY was provider-rejected in native daily source: {year}"
            )

        frame = pd.read_parquet(
            canonical_path,
            columns=[
                "symbol",
                "session_date",
                "close",
                "provider",
                "dataset",
                "timeframe",
                "session_segment",
                "is_adjusted",
                "source_id",
            ],
        )
        frame["session_date"] = pd.to_datetime(
            frame["session_date"], errors="raise"
        ).dt.date
        frame = frame.loc[
            (frame["symbol"].astype(str) == "SPY")
            & frame["session_date"].isin(requested)
        ].copy()
        if not frame.empty:
            expected_source_id = (
                f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit_id}"
            )
            provenance_bad = (
                (frame["provider"].astype(str) != "alpaca")
                | (frame["dataset"].astype(str) != "stock_daily_aggregates")
                | (frame["timeframe"].astype(str) != "1d")
                | (frame["session_segment"].astype(str) != "regular")
                | frame["is_adjusted"].astype(bool)
                | (frame["source_id"].astype(str) != expected_source_id)
            )
            if provenance_bad.any():
                raise SuccessorSpyBenchmarkSourceError(
                    f"native SPY daily provenance drifted: {year}"
                )
            pieces.append(frame[["session_date", "close"]])
        unit_bindings.append(
            {
                "year": year,
                "unit_id": unit_id,
                "canonical_locator": _project_locator(project_root, canonical_path),
                "canonical_sha256": expected_sha,
            }
        )

    fallback = (
        pd.concat(pieces, ignore_index=True)
        if pieces
        else pd.DataFrame(columns=["session_date", "close"])
    )
    if fallback.duplicated(["session_date"]).any():
        raise SuccessorSpyBenchmarkSourceError("native SPY daily fallback has duplicate sessions")
    fallback["close"] = pd.to_numeric(
        fallback["close"], errors="coerce"
    ).astype("float64")
    bad_close = (
        fallback["close"].isna()
        | (fallback["close"] <= 0.0)
        | ~fallback["close"].map(math.isfinite)
    )
    if bad_close.any():
        raise SuccessorSpyBenchmarkSourceError(
            "native SPY daily fallback contains invalid closes"
        )
    return fallback, {
        "research_daily_source_fingerprint": str(
            research_manifest["source_fingerprint"]
        ),
        "native_acceptance_fingerprint": expected_native_fingerprint,
        **plan_report,
        "unit_count": len(unit_bindings),
        "unit_bindings": unit_bindings,
        "unit_bindings_fingerprint": canonical_sha256(unit_bindings),
        "protected_or_future_daily_partition_opened": False,
    }


'''
    text = text[:fn_start] + replacement + text[fn_end:]
    text = text.replace(
        '"replacement_source": "SPLIT_ADJUSTED_DAILY",',
        '"replacement_source": "NATIVE_RAW_DAILY",',
    )
    if "SPLIT_ADJUSTED_DAILY" in text or "split-adjusted" in text.lower():
        raise RuntimeError("source module still contains split-adjusted fallback wording")
    path.write_text(text, encoding="utf-8")


def patch_cli() -> None:
    path = ROOT / "scripts/run_successor_spy_source_audit.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '"split_daily_source_fingerprint": scientific["daily_fallback"].get(\n                    "split_daily_source_fingerprint"\n                ),',
        '"native_acceptance_fingerprint": scientific["daily_fallback"].get(\n                    "native_acceptance_fingerprint"\n                ),',
        "CLI native fingerprint",
    )
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "tests/test_successor_spy_benchmark_source.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("split_daily_repair", "native_daily_repair")
    text = text.replace('"SPLIT_ADJUSTED_DAILY"', '"NATIVE_RAW_DAILY"')
    text = text.replace("split_daily_fallback", "native_daily_fallback")
    path.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    replacements = {
        ROOT / "README.md": [
            ("split-adjusted V2 daily close", "raw canonical V2 daily close"),
            ("2026 split-daily partitions", "2026 native-daily partitions"),
        ],
        ROOT / "docs/roadmap.md": [
            ("split-adjusted V2 daily SPY close", "raw canonical V2 daily SPY close"),
            ("2026 split-daily partition", "2026 native-daily partition"),
        ],
        ROOT / "docs/strategy_evidence_register.md": [
            ("split-adjusted V2 daily SPY close", "raw canonical V2 daily SPY close"),
            ("2026 split-daily partition", "2026 native-daily partition"),
        ],
    }
    for path, pairs in replacements.items():
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_source()
    patch_cli()
    patch_tests()
    patch_docs()
    (ROOT / "scripts/_pr86_refine_native_daily.py").unlink(missing_ok=True)
    (ROOT / ".github/workflows/pr86-refine-native-daily.yml").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
