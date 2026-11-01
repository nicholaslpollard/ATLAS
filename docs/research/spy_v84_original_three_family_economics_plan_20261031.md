# V84 – Source-verified offline SPY option quote-reference economics (2026-10-31)

## Frozen input and interpretation

V84 consumes the original V83 v2 `entry_screen.json`, `option_source_plan.json`, `source_receipts.json`, and `summary.json`. It verifies the SHA signatures of all four reports, their mutual links, all 101 exact query receipts, and every V38 immutable original archive before it can model a price. It does **not** run an options GET, trade, broker call, account deposit/withdrawal, or try to repair incomplete historical sources. A failed cache SHA or missing original is a **fatal source failure** rather than an invented outcome.

The initial 2025 H2 candidate screen is **development data**, not holdout. Signals: 45 opening-range continuation, 51 failed-breakout fade, 5 gap fade. The three 13:00 close days have 12:05 research-source cutoffs. No completed option trade or verified alpha is implied by archived data.

## Predeclared independent experiment (no shared cash yet)

- Examine 1s original SPY ATM 0DTE contract quotes for each original 09:35:01 or 09:40:01 completed-bar signal. Maximum 10 seconds to find a valid discovery quote; require 1s or 3s registered action lag with at most 3 additional seconds to find a qualified action quote. A >1% adverse entry-ask change **rejects** the hypothetical entry.
- Quote quality is inherited from V55: valid timestamp and exact contract, positive bid/ask and displayed sizes, noncrossed spread of at most 15%. Do not use future option observations to choose the contract or fill an entry.
- Use observed action ASK for hypothetical entry and observed exit action BID for hypothetical exit, with fixed $0.65/contract/side and $500 per-signal premium limit; quantities 1–4 limited by entry ask size. No hidden fills, option exercise cash, commissions other than the registered $0.65, partial fills, or market impact are asserted.
- Three registered nonoptimized V76 exit controls: `control_50_100` (−50% stop / +100% take, trail arm +20%, trail −15%), `balanced_35_100` (−35% stop / +100% take, trail arm +20%, trail −15%), and `runner_35_150` (−35% stop / +150% take, trail arm +30%, trail −20%). Respect their original 180/120/180-minute maximum holds.
- Exit trading window: planned exit 15:00 ET and research last attempt 15:05 on a normal day; 12:00 / 12:05 ET on a 13:00 shortened NYSE day. Stop observing after the hard cutoff. Trigger at the observed BID, then 1s/3s latency; original trigger limit is only immediately marketable when action BID is at least trigger BID. Otherwise flag `requires_new_lower_limit_if_false` and report BID-reference P&L *only as a repriced shadow*, not a fill.
- Report two distinct *hypothetical* economics: observed action BID and a 2% adverse BID haircut. Preserve all no-entry and unresolved outcomes (including source gaps, bad quotes and missing action liquidity) as censored, never as zero cash losses or free capital.
- Compressed SHA-linked event journals for all 101 × 3 × 2 = 606 independent scenarios. Hold decisions are sampled every 60 original tape rows to bound storage, while all input quote observations are inspected and invalid quotes, decisions and actions are logged. Original complete immutable quote streams remain in V38; this review ZIP never duplicates the provider source bytes.
- Signed `candidate_outcomes.json`, `window_economics.json` (overall, ISO week, month, year) and `summary.json`. Profitability is calculated **closed-only**, with no-entry/censored counts alongside it. There is no double-counted realized portfolio P&L, shared account cash, exercise, execution guarantee, production promotion, or unused source reuse claim.

### One workstation command after PR acceptance

From ATLAS project root using the normal .venv:

```powershell
python -m scripts.run_spy_v84_offline_three_family_economics `
  --campaign-dir data/research/spy_v83_source_first_2025h2_20261031_173217 `
  --output-dir data/research/spy_v84_offline_2025h2_FIRST_RUN
```

Choose a **new immutable** output folder for any rerun. The command makes zero provider or broker calls. Upload only the evidence ZIP, not the raw V38 quote tapes. This is a research diagnostic; inspect censoring, entry/exit gaps, marketability and cost/haircut sensitivity before building any portfolio-capital ledger or parameter tuning.
