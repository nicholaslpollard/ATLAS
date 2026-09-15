from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_function(path: Path, start_marker: str, end_marker: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    path.write_text(text[:start] + replacement.rstrip() + "\n\n" + text[end + 2 :], encoding="utf-8")


def patch_analyzer() -> None:
    path = ROOT / "packages/backtesting/successor_selected_minute_path_analysis.py"
    replacement = r'''def _selected_assignments(project_root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    conditioning_binding = validate_conditioning_inputs(project_root)
    root = conditioning_root(project_root)
    assignment_path = root / "eligibility_assignments.parquet"
    normalized_glob = root / "normalized" / "*.parquet"
    conn = duckdb.connect()
    try:
        frame = conn.execute(
            f"""
            WITH selected AS (
                SELECT fold_id, policy_id, economic_family_id, native_timeframe,
                       instrument_key, ticker, session_date, direction,
                       comparable, primary_net_return, stress_net_return
                FROM read_parquet('{_sql_path(assignment_path)}')
                WHERE research_eligible AND comparable AND native_timeframe='1m'
            )
            SELECT
                a.fold_id, a.policy_id, a.economic_family_id, a.native_timeframe,
                a.instrument_key, a.ticker, a.session_date, a.direction,
                o.gross_return,
                a.primary_net_return,
                a.stress_net_return,
                o.mfe,
                o.mae,
                o.entry_time_utc,
                o.exit_time_utc,
                o.holding_minutes,
                o.comparable AS normalized_comparable,
                (a.primary_net_return IS NOT DISTINCT FROM o.primary_net_return)
                    AS primary_return_binding_matches,
                (a.stress_net_return IS NOT DISTINCT FROM o.stress_net_return)
                    AS stress_return_binding_matches
            FROM selected a
            JOIN read_parquet('{_sql_path(normalized_glob)}', union_by_name=true) o
              ON o.policy_id = a.policy_id
             AND o.native_timeframe = a.native_timeframe
             AND o.instrument_key = a.instrument_key
             AND o.session_date = a.session_date
             AND o.direction = a.direction
            ORDER BY a.policy_id, a.direction, a.instrument_key, a.session_date, a.fold_id
            """
        ).fetchdf()
    finally:
        conn.close()
    if len(frame) != EXPECTED_SELECTED_MINUTE_COMPARABLE:
        raise SuccessorSelectedMinutePathError(
            f"selected minute population/join drifted: {len(frame)} != {EXPECTED_SELECTED_MINUTE_COMPARABLE}"
        )
    policies = sorted(str(value) for value in frame["policy_id"].dropna().unique())
    if policies != [EXPECTED_POLICY_ID]:
        raise SuccessorSelectedMinutePathError(f"selected minute policy drifted: {policies}")
    if not bool(frame["normalized_comparable"].all()):
        raise SuccessorSelectedMinutePathError(
            "selected minute comparability drifted from normalized opportunities"
        )
    if not bool(frame["primary_return_binding_matches"].all()) or not bool(
        frame["stress_return_binding_matches"].all()
    ):
        raise SuccessorSelectedMinutePathError(
            "selected minute retained return binding drifted from normalized opportunities"
        )
    frame = frame.drop(
        columns=[
            "normalized_comparable",
            "primary_return_binding_matches",
            "stress_return_binding_matches",
        ]
    )
    if frame[["entry_time_utc", "exit_time_utc", "gross_return", "holding_minutes"]].isna().any().any():
        raise SuccessorSelectedMinutePathError("selected minute population has missing retained path fields")
    frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
    frame["entry_time_utc"] = pd.to_datetime(frame["entry_time_utc"], utc=True, errors="raise")
    frame["exit_time_utc"] = pd.to_datetime(frame["exit_time_utc"], utc=True, errors="raise")
    if bool((frame["exit_time_utc"] < frame["entry_time_utc"]).any()):
        raise SuccessorSelectedMinutePathError("selected minute exit precedes entry")
    duplicates = int(
        frame.duplicated(
            subset=["fold_id", "policy_id", "direction", "instrument_key", "session_date"]
        ).sum()
    )
    if duplicates:
        raise SuccessorSelectedMinutePathError(f"selected minute population has {duplicates} duplicate keys")
    frame["case_id"] = [
        canonical_sha256(
            {
                "fold_id": int(row.fold_id),
                "policy_id": str(row.policy_id),
                "direction": str(row.direction),
                "instrument_key": str(row.instrument_key),
                "session_date": row.session_date.isoformat(),
                "entry_time_utc": pd.Timestamp(row.entry_time_utc).isoformat(),
                "exit_time_utc": pd.Timestamp(row.exit_time_utc).isoformat(),
            }
        )[:24]
        for row in frame.itertuples(index=False)
    ]
    if frame["case_id"].duplicated().any():
        raise SuccessorSelectedMinutePathError("selected minute case id collision")
    return frame, conditioning_binding'''
    replace_function(path, "def _selected_assignments(", "\n\ndef _input_root", replacement)


def patch_tests() -> None:
    path = ROOT / "tests/test_successor_selected_minute_path_analysis.py"
    text = path.read_text(encoding="utf-8")
    old_imports = "import pandas as pd\nimport pytest\n\nfrom packages.backtesting.successor_selected_minute_path_analysis import _analyze_case_bars\n"
    new_imports = (
        "import duckdb\nimport pandas as pd\nimport pytest\n\n"
        "import packages.backtesting.successor_selected_minute_path_analysis as minute_path\n"
        "from packages.backtesting.successor_selected_minute_path_analysis import _analyze_case_bars\n"
    )
    if old_imports not in text:
        raise RuntimeError("minute path test import anchor drifted")
    text = text.replace(old_imports, new_imports, 1)
    addition = r'''


def test_selected_assignments_rejoins_compact_selector_to_normalized_path_fields(
    tmp_path, monkeypatch
) -> None:
    assignments_path = tmp_path / "eligibility_assignments.parquet"
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()
    normalized_path = normalized_dir / "minute_0000.parquet"

    rows = EXPECTED_SELECTED_MINUTE_COMPARABLE
    session = date(2026, 1, 5)
    entry = pd.Timestamp("2026-01-05T14:45:00Z")
    assignments = pd.DataFrame(
        {
            "fold_id": list(range(1, rows + 1)),
            "policy_id": [EXPECTED_POLICY_ID] * rows,
            "economic_family_id": ["opening_range_breakout"] * rows,
            "native_timeframe": ["1m"] * rows,
            "instrument_key": [f"T{index:04d}" for index in range(rows)],
            "ticker": [f"T{index:04d}" for index in range(rows)],
            "session_date": [session] * rows,
            "direction": ["LONG"] * rows,
            "comparable": [True] * rows,
            "primary_net_return": [0.01] * rows,
            "stress_net_return": [0.005] * rows,
            "research_eligible": [True] * rows,
        }
    )
    normalized = pd.DataFrame(
        {
            "policy_id": [EXPECTED_POLICY_ID] * rows,
            "economic_family_id": ["opening_range_breakout"] * rows,
            "native_timeframe": ["1m"] * rows,
            "instrument_key": [f"T{index:04d}" for index in range(rows)],
            "ticker": [f"T{index:04d}" for index in range(rows)],
            "session_date": [session] * rows,
            "direction": ["LONG"] * rows,
            "comparable": [True] * rows,
            "gross_return": [0.015] * rows,
            "primary_net_return": [0.01] * rows,
            "stress_net_return": [0.005] * rows,
            "mfe": [0.03] * rows,
            "mae": [-0.02] * rows,
            "entry_time_utc": [entry] * rows,
            "exit_time_utc": [entry + pd.Timedelta(minutes=30)] * rows,
            "holding_minutes": [30] * rows,
        }
    )
    conn = duckdb.connect()
    try:
        conn.register("assignments_frame", assignments)
        conn.execute(
            f"COPY assignments_frame TO '{assignments_path.as_posix()}' (FORMAT PARQUET)"
        )
        conn.unregister("assignments_frame")
        conn.register("normalized_frame", normalized)
        conn.execute(
            f"COPY normalized_frame TO '{normalized_path.as_posix()}' (FORMAT PARQUET)"
        )
        conn.unregister("normalized_frame")
    finally:
        conn.close()

    monkeypatch.setattr(minute_path, "conditioning_root", lambda _project_root: tmp_path)
    monkeypatch.setattr(
        minute_path,
        "validate_conditioning_inputs",
        lambda _project_root: {"conditioning_analysis_fingerprint": "synthetic"},
    )

    selected, binding = minute_path._selected_assignments(tmp_path)
    assert len(selected) == EXPECTED_SELECTED_MINUTE_COMPARABLE
    assert binding["conditioning_analysis_fingerprint"] == "synthetic"
    assert selected["gross_return"].eq(0.015).all()
    assert selected["mfe"].eq(0.03).all()
    assert selected["mae"].eq(-0.02).all()
    assert selected["holding_minutes"].eq(30).all()
    assert selected["entry_time_utc"].notna().all()
    assert selected["exit_time_utc"].notna().all()
'''
    if "test_selected_assignments_rejoins_compact_selector_to_normalized_path_fields" in text:
        raise RuntimeError("minute assignment join regression test already exists")
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


def patch_docs() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    marker = "### Successor selected-path evidence — COMPLETE / NO PROMOTION (2026-09-15)\n"
    note = (
        "\n**Exact-minute execution repair (2026-09-15).** The first exact-minute invocation stopped before any minute source read because the compact `eligibility_assignments.parquet` selector artifact intentionally does not persist `gross_return`, MFE/MAE, or entry/exit timestamps. The minute diagnostic now re-joins those selected assignments to the already SHA-validated normalized opportunity artifacts on the same unique conditioning key used by the accepted option-worthiness analysis (`policy_id`, `native_timeframe`, `instrument_key`, `session_date`, `direction`). Return/comparability bindings are checked before path construction. No minute result was opened by the failed invocation and all research/trading authority remains unchanged.\n"
    )
    if note.strip() not in text:
        if marker not in text:
            raise RuntimeError("README selected-path marker drifted")
        text = text.replace(marker, marker + note, 1)
        readme.write_text(text, encoding="utf-8")

    roadmap = ROOT / "docs/roadmap.md"
    text = roadmap.read_text(encoding="utf-8")
    marker = "## Successor selected-path closeout and exact-minute continuation — 2026-09-15\n"
    note = (
        "\n**Execution repair:** the first exact-minute invocation failed safely at the selector-artifact read because `eligibility_assignments.parquet` is intentionally compact and does not carry retained gross/path fields. The repaired reader now uses the accepted option-worthiness join discipline to bind each selected assignment back to its SHA-validated normalized opportunity before any native minute source is opened. A regression test reproduces the compact-selector schema. The failed attempt opened no minute evidence and changed no authority.\n"
    )
    if note.strip() not in text:
        if marker not in text:
            raise RuntimeError("roadmap selected-path marker drifted")
        text = text.replace(marker, marker + note, 1)
        roadmap.write_text(text, encoding="utf-8")


def main() -> None:
    patch_analyzer()
    patch_tests()
    patch_docs()


if __name__ == "__main__":
    main()
