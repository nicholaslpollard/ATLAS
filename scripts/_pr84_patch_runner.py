from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} occurrence(s), found {count}")
    return text.replace(old, new)


runner_path = Path("packages/backtesting/successor_development_runner.py")
runner = runner_path.read_text(encoding="utf-8")
runner = replace_exact(
    runner,
    "from packages.core.settings import Settings, load_settings",
    "from packages.core.settings import AtlasSettings, load_settings",
    "AtlasSettings import",
)
runner = replace_exact(
    runner,
    "settings: Settings",
    "settings: AtlasSettings",
    "AtlasSettings annotations",
    expected=4,
)
runner = replace_exact(
    runner,
    'frame.to_parquet(temp, index=False)\n        with temp.open("rb") as handle:\n            os.fsync(handle.fileno())',
    'frame.to_parquet(temp, index=False)\n        with temp.open("rb+") as handle:\n            os.fsync(handle.fileno())',
    "Windows parquet fsync mode",
)
runner_path.write_text(runner, encoding="utf-8")

engine_path = Path("packages/backtesting/successor_development_engine.py")
engine = engine_path.read_text(encoding="utf-8")
engine = replace_exact(
    engine,
    "from packages.backtesting.b35_development_context import DailySessionSummary",
    "from packages.backtesting.b35_development_context import build_condition_snapshot",
    "retained B35 context import",
)
old_context = '''                "context": {\n                    "legacy_b35_signal_time_et": str(_signal_time_override(setup, bars, session_date)),\n                },'''
new_context = '''                "context": asdict(\n                    build_condition_snapshot(\n                        setup,\n                        bars,\n                        symbol=symbol,\n                        session_date=session_date,\n                        prior_daily=retained_history.daily,\n                        current_regular_open=current_open,\n                        current_split_factor=current_epoch,\n                        prior_market_regime="UNAVAILABLE",\n                        signal_time_et_override=_signal_time_override(\n                            setup, bars, session_date\n                        ),\n                    )\n                ),'''
engine = replace_exact(
    engine,
    old_context,
    new_context,
    "retained B35 full condition context",
)
engine_path.write_text(engine, encoding="utf-8")
