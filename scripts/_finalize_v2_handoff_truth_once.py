from pathlib import Path

root = Path(__file__).resolve().parents[1]
readme_path = root / "README.md"
workflow_path = root / ".github" / "workflows" / "v2-handoff-truth-once.yml"
self_path = Path(__file__).resolve()

text = readme_path.read_text(encoding="utf-8")
old = """These results may inform future work but may not be retuned into positive findings.\nThe protected holdout remains unconsumed as of this repository handoff; the\nauthorized local walk-forward command will change that status permanently and its\nreceipt becomes the authority for the workstation result. LIVE and automatic broker\nfailover remain disabled.\n"""
new = """These results may inform future work but may not be retuned into positive findings.\nThe retained master holdout was subsequently consumed exactly once by the frozen\nA33/B33 V2 walk-forward on 2026-09-07; that consumption does not rewrite the\nseparate earlier branch statements below, which correctly record zero protected\nreturn reads for those experiments. LIVE and automatic broker failover remain\ndisabled.\n"""
if old not in text:
    raise SystemExit("missing final holdout handoff anchor")
text = text.replace(old, new, 1)
old2 = "- Alpaca SIP V2 is now the immediate data-foundation priority. Empirical sizing\n"
new2 = "- Alpaca SIP V2 daily source/replay preparation is complete; the next V2 data task is the finite B34 minute/intraday semantics audit. Empirical sizing\n"
if old2 not in text:
    raise SystemExit("missing V2 priority anchor")
text = text.replace(old2, new2, 1)
readme_path.write_text(text.rstrip() + "\n", encoding="utf-8")

workflow_path.unlink(missing_ok=True)
self_path.unlink(missing_ok=True)
