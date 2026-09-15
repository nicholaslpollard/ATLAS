from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

README_SECTION = r'''

## Exact-minute ORB closeout and literature-fidelity v2 freeze — 2026-09-15

The selected-minute diagnostic is complete under analysis fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`. It reopened only the 259 already-selected/comparable DEVELOPMENT `orb_15m_close_retest_v2` opportunities, verified 218 bound native minute units by exact path and SHA-256, and read 55,581 entry-to-exit minute bars. The consumed master and future blind remained closed.

The exact path result diagnoses a **direction/order failure, not a lack-of-movement failure**. LONG (`n=157`) finished at -0.71% gross / -1.20% primary / -1.70% stress with 8.82% MFE and 7.78% MAE; favorable-first frequency fell from 48.41% at 1% to 40.76% at 5%. SHORT (`n=102`) finished at -0.01% gross / -0.51% primary / -1.01% stress with 3.85% MFE and 3.88% MAE; favorable-first frequency fell from 42.16% at 1% to 29.41% at 5%. Large moves occur, but the retained directional retest entry does not order those moves favorably often enough to justify leverage or an option-expression rescue. Historical option P&L remains unclaimed.

The next opening-range revision is therefore **not** another 15-minute retest parameter tweak. ATLAS preserves `orb_stocks_in_play_5m_v1` unchanged and preregisters a separate `orb_stocks_in_play_5m_literature_v2`, anchored to Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market* (Swiss Finance Institute Research Paper 24-98 / SSRN 4729284). The v2 freezes: first-five-minute range; price > $5; prior-14-session average share volume >= 1,000,000; prior ATR14 > $0.50; first-five-minute relative volume versus the prior 14-session average >= 1.0; top-20 daily relative-volume rank; first-candle direction with doji abstention; direction-specific stop entry at the opening-range boundary; 10% ATR14 stop; and end-of-day exit. ATLAS retains its stricter 0/10/25/50/100-bps cost grid with 50/100 bps primary/stress diagnostics.

The frozen pre-outcome contract fingerprint is `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`. This is a DEVELOPMENT-only, B35/opening-range-motivated challenger. Because both the internal diagnosis and the published study overlap DEVELOPMENT-era evidence, DEVELOPMENT can diagnose this v2 but cannot self-validate or promote it. Master/future/provider/broker/PAPER/LIVE/confluence/option-trading authority remains zero/false.
'''

ROADMAP_SECTION = r'''

## Exact-minute ORB diagnosis and bounded literature-fidelity revision — 2026-09-15

The 259-case selected `orb_15m_close_retest_v2` minute-path diagnostic completed under fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8` after exact SHA verification of 218 native units and 55,581 path bars. LONG was -0.71% gross / -1.20% primary / -1.70% stress; SHORT was -0.01% / -0.51% / -1.01%. Favorable-first frequency was below 50% at every 1/2/3/5% threshold in both directions and generally worsened with threshold size. The opening-range retest failure is therefore localized to directional/path ordering rather than insufficient move magnitude.

The bounded next research action is `orb_stocks_in_play_5m_literature_v2`, preserved separately from `orb_stocks_in_play_5m_v1`. Its pre-outcome contract is frozen at `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb` and follows the literature mechanism rather than a parameter sweep: five-minute range, PIT 14-session share-volume/ATR/opening-relative-volume inputs, RV >= 1.0, daily top-20 RV rank, opening-candle direction, directional stop entry, 0.10 x ATR14 stop, and EOD exit. Gap-through entries fill at the worse first post-09:35 bar open; same-minute entry/stop ordering will remain unresolved/noncomparable rather than be assigned favorably.

Next implementation order:
1. Build a DEVELOPMENT-only cross-sectional runner that computes all v2 eligibility/ranking facts at 09:35 ET from prior-only evidence and accepted native minute sources.
2. Reconstruct exact direction-specific stop entries and exits with the frozen ambiguity rule and ATLAS 0/10/25/50/100-bps costs (50/100 primary/stress).
3. Report signal quality plus minute path/option-worthiness diagnostics; do not claim historical option P&L without PIT option-chain evidence.
4. Treat any DEVELOPMENT result as research diagnosis only. Do not reuse the consumed master, open the future blind, promote the strategy, or open confluence to rescue it.
5. After this one bounded ORB revision, move on rather than continue iterative ORB parameter tuning; Track A simulator/control-plane work remains independent and should continue.
'''

EVIDENCE_SECTION = r'''

## 10. Exact-minute ORB closeout and literature-fidelity v2 preregistration — 2026-09-15

### 10.1 Exact-minute selected-path result

The frozen selected-minute contract reopened exactly 259 already-selected/comparable `orb_15m_close_retest_v2` DEVELOPMENT opportunities spanning 208 symbols. It verified 218 serialized native minute-unit bindings by exact path and SHA-256 before reading 55,581 retained entry-to-exit minute bars. Analysis fingerprint: `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`.

First-touch resolution is minute-bar timestamp. If favorable and adverse thresholds are both touched in the same minute, their order remains unresolved. Exit-bar high/low extremes are excluded so post-exit movement cannot contaminate path evidence.

- LONG (`n=157`): gross -0.71%; primary -1.20%; stress -1.70%; median hold 336m; MFE 8.82%; MAE 7.78%. Favorable-threshold hit / favorable-first / median time: 1% = 89.17% / 48.41% / 1m; 2% = 78.34% / 46.50% / 6m; 3% = 72.61% / 42.04% / 12m; 5% = 54.78% / 40.76% / 16.5m.
- SHORT (`n=102`): gross -0.01%; primary -0.51%; stress -1.01%; median hold 359m; MFE 3.85%; MAE 3.88%. Favorable-threshold hit / favorable-first / median time: 1% = 74.51% / 42.16% / 7.5m; 2% = 59.80% / 41.18% / 20m; 3% = 50.98% / 36.27% / 26.5m; 5% = 31.37% / 29.41% / 31m.

**Diagnosis:** movement magnitude is not the binding failure. The selected retest route frequently experiences substantial movement, but adverse movement wins the race more often than favorable movement at every symmetric threshold. LONG is highly two-sided/noisy; SHORT is approximately gross-flat and negative after realistic costs. Directional leverage or option convexity does not repair an entry whose path ordering is wrong. No historical option P&L is claimed.

### 10.2 Targeted external research and preserved v1

Failure-specific research identified Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market* (Swiss Finance Institute Research Paper 24-98; SSRN 4729284). Their U.S.-stock study focuses on a five-minute ORB and reports the main improvement from restricting trades to unusually active "Stocks in Play" using first-five-minute relative volume and a daily top-20 rank. The studied rule uses first-five-minute candle direction, a direction-specific stop entry at the range boundary, a 10% ATR14 stop, and EOD exit.

ATLAS already has `orb_stocks_in_play_5m_v1`, but that frozen challenger is materially different: it uses a 20-session median opening-volume proxy, a 2.0 relative-volume threshold, a prior-dollar-volume quality gate, and the first closing breakout in either direction. That prior version remains immutable. It is not renamed or retroactively treated as the published design.

### 10.3 `orb_stocks_in_play_5m_literature_v2` frozen hypothesis

A separate version is preregistered before any v2 outcome is opened. Contract fingerprint: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`.

Frozen rules:
- opening range = regular-session 09:30 through 09:34 ET, known at 09:35;
- opening price > $5;
- prior 14-session average daily share volume >= 1,000,000 shares;
- prior ATR14 > $0.50;
- current first-five-minute volume / prior 14-session mean first-five-minute volume >= 1.0;
- daily cross-sectional relative-volume rank <= 20;
- first-five-minute candle positive -> LONG only; negative -> SHORT only; doji -> abstain;
- stop entry at the corresponding opening-range high/low after 09:35;
- a gap through the stop fills at the first post-09:35 minute open rather than receiving the stale stop price;
- stop loss = 0.10 x prior ATR14 from executed entry;
- if not stopped, exit at the last regular-session bar;
- same-minute entry-and-stop ordering is unresolved/noncomparable unless a later pre-outcome contract explicitly chooses a conservative information-safe convention;
- one trade maximum per symbol/session;
- ATLAS costs remain 0/10/25/50/100 bps, with 50/100 bps primary/stress for intraday research;
- 1/2/3/5% exact-minute path thresholds remain descriptive option-worthiness inputs only.

### 10.4 Scientific status and authority

This v2 is intentionally a bounded mechanistic revision, not a sweep of opening-range lengths, relative-volume cutoffs, ATR stops, or exits. The internal motivation is post-result DEVELOPMENT evidence, while the external paper itself studies 2016-2023 and therefore overlaps ATLAS DEVELOPMENT. A positive DEVELOPMENT result can support specialization/research continuation but **cannot independently validate or promote the strategy**. Untouched/prospective evidence is required later.

Consumed-master reads = 0; future-blind reads = 0; provider reads = 0; broker reads/writes = 0. Strategy/selector promotion, confluence, PAPER, LIVE, and option-trading authority all remain false.
'''


def append_once(path: Path, marker: str, section: str) -> None:
    text = path.read_text(encoding="utf-8").rstrip()
    if marker in text:
        raise RuntimeError(f"section already present in {path}")
    path.write_text(text + section.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    append_once(ROOT / "README.md", "## Exact-minute ORB closeout and literature-fidelity v2 freeze", README_SECTION)
    append_once(ROOT / "docs" / "roadmap.md", "## Exact-minute ORB diagnosis and bounded literature-fidelity revision", ROADMAP_SECTION)
    append_once(ROOT / "docs" / "strategy_evidence_register.md", "## 10. Exact-minute ORB closeout and literature-fidelity v2 preregistration", EVIDENCE_SECTION)


if __name__ == "__main__":
    main()
