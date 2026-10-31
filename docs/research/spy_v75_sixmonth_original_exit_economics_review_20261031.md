# ATLAS V75 — Six-month original-tape dynamic exit and execution-friction evidence

**Audit date:** 2026-10-31. **Evidence:** Uploaded original signed V69 (March and June), V73 (January, February, April, May), and V74 1-second/3-second full-scope cohort summaries and selected June 4/13 per-trade event reports. This is an independent analysis of retained historical original-source **quote-reference** simulations, not broker fills, actual Webull-versus-Alpaca execution, or validated market alpha. The offline audit performed **zero provider calls and zero broker orders**. A reproducible standalone `atlas_v75_crossmonth_audit.py`, signed `summary.json`, signed `daily_comparisons.json` (246 day/latency records), and detailed `REVIEW.md` were produced from the six uploaded monthly source ZIPs and V74 campaign ZIP.

## Workstation acceptance: what is actually proved

The V73/V74 campaign ran on the workstation against pinned development commit `ecc4da8f996fee49d58ca199d449b184e4986350`. The original Jan/Feb/Apr/May local source barriers were eliminated by using actual XNYS sessions, without missing genuine open-session native minute evidence. All original full stock-source SHA gates passed; **47 newly selected exact option requests** were issued, dispatched and archived (12 January, 11 February, 12 April, 12 May); no unqualified/missing sources persisted in those four newly acquired cohorts. March retains its 12 archived sources plus the explicit NO_DATA for **2025-03-31**; June's 13 selected original tapes were archived. V74 reads original cache only; both broker labels reuse one identical quote model.

Independent source audit verified the signed five-document preflight/source/replay/chunk/root lineage across all six source months, the signed 24-campaign JSON receipts, parent session/selected-contract/entry fingerprint matching, original position quantities and dynamic lag identities. All **123 market sessions × 2 lags = 246 daily comparisons** passed those checks. The full option source archive bytes exist on the user's workstation, not in the uploaded ZIPs; the workstation V74 source SHA checks passed when it ran. The original source requests must not be blindly reissued.

## Frozen baseline versus V74: 2025 Jan–Jun

| Month | V55/V65 fixed-exit P&L on ORIGINAL closed subset | V74 1s closed trades | V74 3s closed trades |
|---|---:|---:|---:|
| January | -$728.80 | -$390.70 | -$383.70 |
| February | -$258.30 | -$747.50 | -$778.50 |
| March | +$78.40 | -$204.70 | -$183.70 |
| April | -$394.10 | -$521.40 | -$508.40 |
| May | -$561.10 | -$960.80 | -$947.80 |
| June | +$349.30 | +$327.50 | +$318.50 |
| **Sum of modeled closed subset economics** | **-$1,514.60** | **-$2,497.60** | **-$2,483.60** |

These totals are **not a six-month account equity series**. The original baseline censored **17 exits**, so fixed-exit P&L includes only 38 closed cases while V74 records 55 modeled closes, 17 NO_ENTRY, 50 NO_SIGNAL and **one missing exact-source day (March 31)**. This missing day makes March and any unbroken six-month cash chain unresolved. Months' stand-alone capital reports each reset at $25,000; no fictitious account join across missing days is permitted.

**Matched comparisons matter:** On the exact **38 originally closed trades** V74 1-second produced -$1,241.60 versus V55 -$1,514.60, a post-hoc favorable $273.00 difference. On the 17 formerly quote-censored cases V74 modeled a further **-$1,256.00**, exposing losses that V55 could not previously measure. June 4 and June 13 first recovered 10:00:01 invalid quote status via later qualified quote observations (10:00:06/10:00:02), but their eventual V74 modeled exits were **10:06:24 ET** (-$253.20) and **10:21:57 ET** (+$25.40) respectively at 1-second latency. Neither later mark equals a broker fill or proves an executable 10:00 exit.

**Win/loss distribution:** 30 positive / 25 negative 1-second modeled closes; average winner **+$73.69**, average loser **-$188.34**, gross modeled **profit factor 0.4695** (3-second 0.4717). Exit reason breakdown: 20 baseline stops total **-$4,204.80**; 30 causal trailing-profit exits total **+$1,201.30**; 2 baseline profit targets **+$996.30**; 3 max-hold time exits **-$490.40**. These are descriptive correlations after observing outcomes, not validated optimization signals. The monthly and weekly breakdowns are in the signed audit; 16 of 26 ISO calendar weeks had negative aggregate modeled closed-trade P&L in the 1-second study. The 3-second version is only **$14 better** across the reported closed cases; no credible latency-setting superiority has been demonstrated.

## V75 adverse quote execution-price stress

Each shocked exit derives an original quantity and entry debit from signed V65/V69 source-backed trade receipts, and a reference exit bid from V74 fee-aware close cash; an additional adverse percentage reduction of modeled sale-side **BID** is applied without changing signal, actual order/fill authority or quote selection. The preexisting simulated $0.65 per contract per side is retained. **Hypothetical scenario only; do not label executable or historical slippage.**

| Additional adverse exit-bid reduction | V74 1s signed closed-trade P&L | V74 3s signed closed-trade P&L |
|---|---:|---:|
| 0% | -$2,497.60 | -$2,483.60 |
| 0.5% | -$2,598.83 | -$2,584.86 |
| 1% | -$2,700.03 | -$2,686.17 |
| 2% | -$2,902.46 | -$2,888.74 |
| 5% | -$3,509.75 | -$3,496.45 |

Even the optimistic 0%-additional-penalty scenario loses on five of six months. Additional fees, broker option approval, margin/assignment and sell-to-close execution risk remain separately unverified; SPY's physical exercise cannot be booked as a guaranteed cash payout.

## Decisions for the next simulator cycle

1. **Keep** immutable original V55 and V73 source receipts; V74 is an **experimental challenger**, not the profitable strategy. Do not discard or relabel historical losing trades. Keep Webull-primary / Alpaca manually selected fallback; broker-specific option fill and expiration policies have not yet been implemented in live execution.
2. **Before simply widening the same losing cohort**, run an honest entry-signal and exit-loss-asymmetry review. Registration of independent strategy families and exit candidates should precede their next acquisition and outcome inspection. No parameter selection based on post-hoc June successes; candidate-specific source demands are dynamic/cache-first and no arbitrary call caps apply.
3. **Develop realistic order-state research**: decision trigger vs actionable fresh bid, allowed limit repricing, adverse-stop escalation, partial quantity, queue/latency/slippage and exact order reconciliation; no automatic broker switch and no assumption that size available at BID guarantees execution.
4. **Chronological account proof**: multi-month account cash needs source-qualified all eligible days; missing original date remains censored. Weekly/monthly/annual results and independent future periods must be reported by original-signal universe, no-survivorship filters, skipped trade reasons, source blocks, costs and drawdown.
5. **New uninspected evaluation period:** This Jan–Jun 2025 dataset is now observed and is NOT an untouched holdout. Prefer separately frozen future-month 2025 data (subject to original source coverage and strategy-registry gates) after choosing candidates using prior cohorts; protected 2026 outcomes remain protected by earlier requirements.

**Version and authority:** This V75 report records actual user-run research evidence; it changes no existing source acquisition, broker execution code, accepted strategy parameters, or LIVE permissions. The user's 2026-10-31 V73/V74 run was completed and reported fully, with repo restored to `main`. V73/V74 PR #444 passed all 20 checks and merged to `main` at `acfbeb916f38c93ebd110fa35aebce62a9bcd87e`.
