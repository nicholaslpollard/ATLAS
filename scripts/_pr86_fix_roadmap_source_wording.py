from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "docs/roadmap.md"
text = path.read_text(encoding="utf-8")
old = "the already-lineaged V2 split-adjusted daily source"
new = "the already-lineaged raw canonical V2 daily source"
if text.count(old) != 1:
    raise RuntimeError(f"expected one stale roadmap source phrase, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
(ROOT / "scripts/_pr86_fix_roadmap_source_wording.py").unlink(missing_ok=True)
(ROOT / ".github/workflows/pr86-fix-roadmap-source-wording.yml").unlink(missing_ok=True)
