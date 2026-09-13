from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


runner = ROOT / "packages/backtesting/successor_development_runner.py"
replace_once(
    runner,
    "from packages.core.settings import AtlasSettings, load_settings\nfrom packages.core.successor_execution_profile import (\n",
    "from packages.core.settings import AtlasSettings, load_settings\n"
    "from packages.core.successor_execution_profile import (\n",
)
# Insert data helpers after the execution-profile import block, using a stable adjacent import.
replace_once(
    runner,
    "from packages.strategies.successor_implementation_bundle import (\n",
    "from packages.data.duckdb_connection import connect_utc\n"
    "from packages.data.sql import sql_string\n"
    "from packages.strategies.successor_implementation_bundle import (\n",
)
replace_once(
    runner,
    '''def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temp = unique_temp_path(path)\n    try:\n        frame.to_parquet(temp, index=False)\n        with temp.open("rb+") as handle:\n            os.fsync(handle.fileno())\n        replace_with_retry(temp, path)\n    finally:\n        temp.unlink(missing_ok=True)\n    return _sha256_file(path)\n''',
    '''def _duckdb_projection(columns: tuple[str, ...] | None) -> str:\n    if columns is None:\n        return "*"\n    return ", ".join('"' + column.replace('"', '""') + '"' for column in columns)\n\n\ndef _read_parquet_frame(\n    path: Path,\n    *,\n    columns: tuple[str, ...] | None = None,\n) -> pd.DataFrame:\n    con = connect_utc(":memory:")\n    try:\n        return con.execute(\n            f"SELECT {_duckdb_projection(columns)} "\n            f"FROM read_parquet({sql_string(path)}, hive_partitioning=false)"\n        ).fetchdf()\n    finally:\n        con.close()\n\n\ndef _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temp = unique_temp_path(path)\n    con = connect_utc(":memory:")\n    registered = False\n    try:\n        con.register("successor_input_frame", frame)\n        registered = True\n        con.execute(\n            f"COPY (SELECT * FROM successor_input_frame "\n            "ORDER BY instrument_id, session_date, timestamp_utc) "\n            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)"\n        )\n        con.unregister("successor_input_frame")\n        registered = False\n        con.close()\n        con = None\n        with temp.open("rb+") as handle:\n            os.fsync(handle.fileno())\n        replace_with_retry(temp, path)\n    finally:\n        if con is not None:\n            if registered:\n                con.unregister("successor_input_frame")\n            con.close()\n        temp.unlink(missing_ok=True)\n    return _sha256_file(path)\n''',
)
replace_once(
    runner,
    '''        frame = pd.read_parquet(parquet)\n        benchmark_frame = pd.read_parquet(benchmark)\n''',
    '''        frame = _read_parquet_frame(parquet)\n        benchmark_frame = _read_parquet_frame(benchmark)\n''',
)

spy = ROOT / "packages/backtesting/successor_spy_benchmark_source.py"
replace_once(spy, "import math\n", "import math\nimport os\n")
replace_once(
    spy,
    '''def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temp = unique_temp_path(path)\n    con = connect_utc(":memory:")\n    try:\n        con.register("spy_benchmark_frame", frame)\n        con.execute(\n            f"COPY (SELECT * FROM spy_benchmark_frame) TO {sql_string(temp)} "\n            "(FORMAT PARQUET, COMPRESSION ZSTD)"\n        )\n        replace_with_retry(temp, path)\n    finally:\n        con.close()\n        temp.unlink(missing_ok=True)\n    return _sha256_file(path)\n''',
    '''def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temp = unique_temp_path(path)\n    con = connect_utc(":memory:")\n    registered = False\n    try:\n        con.register("spy_benchmark_frame", frame)\n        registered = True\n        con.execute(\n            f"COPY (SELECT CAST(session_date AS DATE) AS session_date, close::DOUBLE AS close "\n            "FROM spy_benchmark_frame ORDER BY session_date) "\n            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)"\n        )\n        con.unregister("spy_benchmark_frame")\n        registered = False\n        con.close()\n        con = None\n        with temp.open("rb+") as handle:\n            os.fsync(handle.fileno())\n        replace_with_retry(temp, path)\n    finally:\n        if con is not None:\n            if registered:\n                con.unregister("spy_benchmark_frame")\n            con.close()\n        temp.unlink(missing_ok=True)\n    return _sha256_file(path)\n''',
)

runner_tests = ROOT / "tests/test_successor_development_runner.py"
append = '''\n\ndef test_runner_parquet_io_uses_duckdb_without_pandas_optional_engines(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    def blocked(*args, **kwargs):\n        raise AssertionError("pandas optional Parquet engine must not be used")\n\n    monkeypatch.setattr(pd, "read_parquet", blocked)\n    monkeypatch.setattr(pd.DataFrame, "to_parquet", blocked)\n    path = tmp_path / "daily.parquet"\n    frame = pd.DataFrame(\n        [\n            {\n                "instrument_id": "B",\n                "session_date": date(2020, 1, 3),\n                "timestamp_utc": pd.Timestamp("2020-01-03T14:30:00Z"),\n                "value": 2.0,\n            },\n            {\n                "instrument_id": "A",\n                "session_date": date(2020, 1, 2),\n                "timestamp_utc": pd.Timestamp("2020-01-02T14:30:00Z"),\n                "value": 1.0,\n            },\n        ]\n    )\n\n    sha256 = runner._write_parquet_atomic(path, frame)\n    loaded = runner._read_parquet_frame(path)\n\n    assert len(sha256) == 64\n    assert loaded["instrument_id"].tolist() == ["A", "B"]\n    assert loaded["value"].tolist() == [1.0, 2.0]\n'''
text = runner_tests.read_text(encoding="utf-8")
if "test_runner_parquet_io_uses_duckdb_without_pandas_optional_engines" in text:
    raise RuntimeError("runner DuckDB Parquet regression already exists")
runner_tests.write_text(text.rstrip() + append + "\n", encoding="utf-8")

spy_tests = ROOT / "tests/test_successor_spy_benchmark_source.py"
replace_once(
    spy_tests,
    '''    frame = pd.DataFrame(\n        [{"session_date": date(2019, 8, 12), "close": 287.44}]\n    )\n''',
    '''    frame = pd.DataFrame(\n        [\n            {"session_date": date(2019, 8, 13), "close": 288.11},\n            {"session_date": date(2019, 8, 12), "close": 287.44},\n        ]\n    )\n''',
)
replace_once(
    spy_tests,
    '''    assert pd.to_datetime(loaded["session_date"], errors="raise").dt.date.tolist() == [\n        date(2019, 8, 12)\n    ]\n    assert loaded["close"].tolist() == [287.44]\n''',
    '''    assert pd.to_datetime(loaded["session_date"], errors="raise").dt.date.tolist() == [\n        date(2019, 8, 12),\n        date(2019, 8, 13),\n    ]\n    assert loaded["close"].tolist() == [287.44, 288.11]\n''',
)

print("expanded PR87 DuckDB Parquet repair applied")
