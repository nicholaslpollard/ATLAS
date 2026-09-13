from __future__ import annotations

from pathlib import Path


readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
old = "scripts\\\\"
new = "scripts\\"
count = readme.count(old)
if count != 7:
    raise SystemExit(f"README scripts-path escaping: expected 7 occurrences, found {count}")
readme_path.write_text(readme.replace(old, new), encoding="utf-8")
