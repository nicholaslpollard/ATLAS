from pathlib import Path

root = Path(__file__).resolve().parents[1]
validator_path = root / "scripts" / "validate_a33_b33_reference_foundation.py"
readme_path = root / "README.md"
roadmap_path = root / "docs" / "roadmap.md"
workflow_path = root / ".github" / "workflows" / "a33-living-doc-transition-repair-once.yml"
self_path = Path(__file__).resolve()

validator = validator_path.read_text(encoding="utf-8")
old = '        _require(text, "protected return rows read: **0**", f"{path} protected boundary")\n'
new = '''        if "protected return rows read: **0**" not in text:\n            # Living documents are current-state handoffs, not frozen Phase-start artifacts.\n            # After the one-time master holdout is legitimately consumed, forcing them\n            # to retain the pre-read zero would make accepted current evidence stale.\n            _require(text, "consumed exactly once", f"{path} post-consumption boundary")\n            _require(text, "93,380", f"{path} post-consumption protected-row accounting")\n'''
if old not in validator:
    raise SystemExit("missing A33/B33 living-doc protected-boundary assertion")
validator = validator.replace(old, new, 1)
validator_path.write_text(validator, encoding="utf-8")

readme = readme_path.read_text(encoding="utf-8")
readme_anchor = '''- A33/B33 foundation implementation is complete and protected by its exact-head\n  acceptance workflow. Historical performance has now been opened only for the\n  frozen V2 DEVELOPMENT and one-time walk-forward versions described below; strategy\n  authority did not change and provider/broker/PAPER/LIVE mutations remain zero.\n'''
readme_note = readme_anchor + '''- A33/B33 compatibility validation now treats living-document protected state as a\n  monotonic lifecycle: before outcome access it requires the original zero-read\n  boundary; after an accepted one-time consumption it requires the current\n  consumption statement and protected-row accounting instead. Frozen policy,\n  authority, and feature fingerprints remain mandatory. This prevents current\n  evidence from being rewritten backward merely to satisfy a historical handoff\n  token.\n'''
if readme_anchor not in readme:
    raise SystemExit("missing README A33/B33 current-state anchor")
readme = readme.replace(readme_anchor, readme_note, 1)
readme_path.write_text(readme.rstrip() + "\n", encoding="utf-8")

roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap_anchor = '''- Frozen A33/B33 V2 master-protected return reads: **93,380**. DEVELOPMENT account\n  replay: **-17.912608%** return / **-20.803073%** max drawdown. Frozen walk-forward\n  account replay through `2026-09-03`: **-8.372772%** return / **-8.372772%** max\n  drawdown. Authority promotion: **none**.\n'''
roadmap_note = roadmap_anchor + '''- A33/B33 compatibility validation distinguishes immutable pre-outcome foundation\n  evidence from the living current-state handoff. It accepts only the original\n  zero-read documentation state before consumption or the exact one-time-consumed\n  state with protected-row accounting afterward; frozen fingerprints and authority\n  boundaries remain unchanged.\n'''
if roadmap_anchor not in roadmap:
    raise SystemExit("missing roadmap A33/B33 current evidence anchor")
roadmap = roadmap.replace(roadmap_anchor, roadmap_note, 1)
roadmap_path.write_text(roadmap.rstrip() + "\n", encoding="utf-8")

workflow_path.unlink(missing_ok=True)
self_path.unlink(missing_ok=True)
