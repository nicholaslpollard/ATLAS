from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "packages/backtesting/b35_intraday_outcomes.py"
text = PATH.read_text(encoding="utf-8")
old = '''    if direction == StrategyDirection.LONG:\n        adverse_entry = entry * (1.0 + half)\n        adverse_exit = exit_price * (1.0 - half)\n        return (adverse_exit - adverse_entry) / adverse_entry\n    adverse_entry_proceeds = entry * (1.0 - half)\n    adverse_cover = exit_price * (1.0 + half)\n    return (adverse_entry_proceeds - adverse_cover) / adverse_entry_proceeds\n'''
new = '''    if direction == StrategyDirection.LONG:\n        adverse_entry = entry * (1.0 + half)\n        adverse_exit = exit_price * (1.0 - half)\n        return (adverse_exit - adverse_entry) / entry\n    adverse_entry_proceeds = entry * (1.0 - half)\n    adverse_cover = exit_price * (1.0 + half)\n    return (adverse_entry_proceeds - adverse_cover) / entry\n'''
if text.count(old) != 1:
    raise RuntimeError("expected exactly one B35 net-return cost block")
PATH.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
