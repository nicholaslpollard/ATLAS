from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "packages/backtesting/successor_spy_benchmark_source.py"
text = path.read_text(encoding="utf-8")
replacements = {
    "refusing 2026-or-later split-daily SPY fallback": "refusing 2026-or-later native-daily SPY fallback",
    "SPY split-daily fallback units do not map one-to-one to requested years": "SPY native-daily fallback units do not map one-to-one to requested years",
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one occurrence of {old!r}, found {count}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
(ROOT / "scripts/_pr86_fix_native_wording.py").unlink(missing_ok=True)
(ROOT / ".github/workflows/pr86-fix-native-wording.yml").unlink(missing_ok=True)
