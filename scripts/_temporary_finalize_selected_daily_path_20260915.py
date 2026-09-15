from pathlib import Path

analysis = Path("packages/backtesting/successor_selected_daily_path_analysis.py")
text = analysis.read_text(encoding="utf-8")
old = 'if int(report.get("protected_rows_read", -1)) != 0:'
new = 'if int(report.get("protected_master_return_rows_read", -1)) != 0:'
if old not in text and new not in text:
    raise SystemExit("daily adapter protected-row guard anchor missing")
analysis.write_text(text.replace(old, new), encoding="utf-8")

sections = {
    "README.md": """

### Successor selected-path timing diagnostic (2026-09-15)

The retained-artifact option-worthiness diagnostic completed successfully with analysis fingerprint `6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`. It confirmed 28 replayed routes / 21 economic families and 36,254 walk-forward-selected comparable opportunities. The retained daily MFE/MAE fields span **through 20 sessions**, so their high 1%/2%/3%/5% favorable-excursion rates must not be interpreted as five-session or option-speed evidence. Losing routes also frequently reached large favorable excursions somewhere in that long window.

The next frozen diagnostic is therefore `successor_selected_daily_path_v1`: it reads only the already-selected comparable **daily** opportunities (35,995; about 99.3% of selections) against the accepted DEVELOPMENT daily lake, enters at the same next-session open, and measures five-session MFE/adverse excursion, first 1%/2%/3%/5% favorable/adverse touch session, session-level first-touch ordering, exit capture versus available MFE, and peak give-back. Same-session high/low collisions remain explicitly unordered because daily bars cannot reveal intraday ordering. This is post-result DEVELOPMENT diagnosis only; it creates no strategy, selector, confluence, PAPER, LIVE, promotion, or option-trading authority. The 259 selected ORB minute opportunities remain deferred to a separate minute-path diagnostic rather than mixing minute and daily path semantics.
""",
    "docs/roadmap.md": """

### Successor path-timing gate — frozen 2026-09-15

The first retained-artifact option-worthiness pass is complete (`analysis_fingerprint=6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`). Its main design finding is that the retained daily MFE/MAE window runs through 20 sessions and is too permissive to answer whether a move is fast enough for the five-session strategy horizon or an options expression. Large eventual favorable excursions are common even among routes with negative five-session expectancy.

Before any strategy revision, run the frozen selected-daily path diagnostic on the 35,995 already-selected comparable daily opportunities. Required outputs are five-session favorable/adverse excursion, first-touch session for 1%/2%/3%/5%, favorable-versus-adverse first-touch classification, five-session exit capture versus MFE, and peak give-back. Daily same-session collisions remain unordered. This gate is diagnostic only and may motivate bounded v2 hypotheses; it cannot retroactively validate a route. Keep confluence closed. The 259 selected intraday ORB opportunities require a separate minute-resolution path package after the daily result.
""",
    "docs/strategy_evidence_register.md": """

### 8.9 Retained option-worthiness closeout and selected daily path preregistration — 2026-09-15

The DEVELOPMENT-only retained-artifact option-worthiness run completed with contract fingerprint `caedb97b7031c70e0aeec1f7fbde6d949b2ab22cd39529876b82d1228fcf8b11` and analysis fingerprint `6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`. Scope was 34,273,432 comparable DEVELOPMENT opportunities, 28,825,473 walk-forward-test comparable opportunities, and 36,254 walk-forward-selected comparable opportunities across the authoritative 28 routes / 21 economic families. No consumed-master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority was opened.

Interpretation is deliberately limited: daily MFE/MAE in the retained standalone evidence is `THROUGH_20_SESSIONS`, while the primary daily return is a separate five-session outcome. The resulting 1%/2%/3%/5% MFE rates are therefore **eventual-excursion diagnostics, not five-session hit rates or option-profit evidence**. Their high values even on negative-expectancy routes indicate that timing, adverse path, exit capture, and regime persistence require diagnosis before parameter changes. No route disposition is upgraded by these excursion rates.

Before opening any five-session path results, the next diagnostic is frozen as `atlas-successor-selected-daily-path-v1-five-session-first-touch-descriptive`. Population is exactly the already-selected comparable daily opportunities (expected 35,995). Entry remains next regular-session open. Horizon is five instrument trading sessions. Thresholds are frozen at 1%, 2%, 3%, and 5% in both favorable and adverse directions. Report first-touch session, favorable/adverse ordering at session resolution, MFE, adverse excursion magnitude, five-session close return, exit-capture ratio, and peak give-back. If both sides touch inside the same daily bar, classify `SAME_SESSION_COLLISION_UNORDERED`; do not infer intraday order. The 259 selected ORB minute opportunities are excluded and deferred to a separate minute-path diagnostic. These are post-result DEVELOPMENT diagnostics only and can form bounded successor hypotheses, never validation or promotion.
""",
}
for name, addition in sections.items():
    path = Path(name)
    body = path.read_text(encoding="utf-8")
    unique = addition.strip().splitlines()[0].lstrip("# ").strip()
    if unique not in body:
        path.write_text(body.rstrip() + addition.rstrip() + "\n", encoding="utf-8")

Path(".github/workflows/_temporary_selected_daily_path_finalize_20260915.yml").unlink(missing_ok=True)
Path("scripts/_temporary_finalize_selected_daily_path_20260915.py").unlink(missing_ok=True)
