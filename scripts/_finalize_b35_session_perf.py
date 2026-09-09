from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "packages/backtesting/b35_development_source.py"
text = source.read_text(encoding="utf-8")
old = "count(*) FILTER (WHERE NOT segment_ok)::BIGINT AS incorrect_session_rows"
new = "count(*) FILTER (WHERE segment_ok IS DISTINCT FROM TRUE)::BIGINT AS incorrect_session_rows"
if text.count(old) != 1:
    raise RuntimeError("B35 segment validation finalizer anchor drifted")
source.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
(root / "scripts/_finalize_b35_session_perf.py").unlink(missing_ok=True)
(root / ".github/workflows/_finalize_b35_session_perf.yml").unlink(missing_ok=True)
