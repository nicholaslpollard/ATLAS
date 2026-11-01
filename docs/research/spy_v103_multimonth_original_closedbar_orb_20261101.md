# ATLAS V103 — Multimonth exact-source V55/V65 0DTE ORB quote experiment

Registered November 1, 2026. Branch `research/v103-multimonth-original-closed-bar-orb-20261101`; based on V102 audit, not yet run on the user workstation. **Code and tests committed, no source or P&L results claimed for V103.**

## Why this is distinct from the failed V99/V101 candidates

The fully audited 21,600 V101 24-hour / seven-day historical news-gated CALL scenarios yielded **0 of 3,356** source-complete configurations profitable across all six cohorts. The seven-day article-count filter accepted every source-backed entry exposure and therefore adds no useful discrimination. Another threshold search on the same CALL families is unlikely to be a good use of time.

V103 broadens an **already implemented, structurally different** SPY 0DTE opening-range entry concept. It **does not invent a new rule or duplicate V51's first-tick ORB**. It calls the existing immutable V55 completed-minute-close 5-minute opening-range rule and V65 SHA-verified minute/source replay. This is the *development* version using a completed 1-minute bar, M/W/F, original ATM strike inferred from the known completed close and 1-second-after-close decision; it is **NOT** the externally reported first tick intraminute ORB, and its bar publication timestamp remains a research assumption. Existing V55 policy is one-day expiry, <=$500 gross option premium, 1s lag, 1% adverse ASK drift cap, 100% target, 50% stop, 15:30 clock exit, fees 0.65 per option contract **per side**. V103 does **not** add V90's later 2% exit-BID haircut; report its returns honestly as original V55 quote-reference, not stressed P&L. No market orders or genuine exchange fills are made.

## One broad default source census

Run 2025-06-01 through 2026-04-30: 11 calendar months, all genuine exchange trading sessions, not ad-hoc weekdays including exchange holidays. **Early closing trading sessions are predeclared exclusions** because V55's frozen 15:30 exit would not be exchange-executable on those days. No 2026 May–August protected master holdout or monthly partitions overlapping it. A user can pass earlier dates via standalone script but the normal runner pins June 2025–April 2026.

For each month, V103:
1. Discover one original native SPY 1-minute SHA-receipted complete monthly source; absence is explicit *stock source missing*, not a no-breakout signal. Ambiguous metadata or invalid SHA stops rather than inventing a clean month.
2. Call unmodified V65 once per month for regular-length exchange sessions. V65 verifies **full original canonical and raw bundle hashes**, validates each SPY session, runs V55 first completed close outside opening 5-minute OHLC range, registers exact ThetaData contract + 1-second 09:36 or later original option tape requirement, and uses the original V38 cache **read only**. No auto-acquisition, paid ThetaData GET or broker order.
3. Categorize signed per-day evidence into genuine week-policy exclusion, qualified no signal, qualified no entry due ASK drift/cost, original quote-modelled closed exit, **missing stock source**, **missing/unqualified option tape**, or **unknown exercise/expiry cash**. An absent archival quote is never assigned a $0 P&L merely because V55 standalone reports NO_ENTRY.
4. Save V65's complete signed original bar decisions, event/quote exit reviews and source references as a **lossless verified gzip** after hashing and verifying decompressed bytes; remove uncompressed temporary JSON **only after verification succeeds**. Keep compact signed per-day source and cash classifications to reduce memory/storage duplication, with parent V65 fingerprint and original per-session SHA.
5. Recompute a separate $25,000 one-slot per-month cash chain. Confirm V55 original entry debit, exit credit, $0.65-per-side commission and net P&L arithmetic, and retain loss/profit weekly/monthly contributions. **The continuous 11-month account is known only if all required prior source/exit cash can be qualified.** At the first missing source/unresolved open option, permanently censor cumulative account equity; later independent monthly diagnostic outcomes are still preserved but are NOT chained across that unknown event.
6. Save individual signed monthly account reports, a cross-month signed chronological cash journal with every original opportunity considered or censored, plus a compact signed summary of source coverage, first global blocker, and archive SHA receipts. Runner creates separate summary and full-source evidence ZIPs even after a partial failure.

## Execution and audit

Modules:
- `packages/simulation/spy_v103_offline_orb_causal_account.py` — signed V65 classification and conservative chronological cash.
- `scripts/run_spy_v103_multimonth_original_closedbar_orb.py` — monthly source discovery, genuine exchange calendar, sha verification through V65, read-only original V38, lossless gzip and signed research outputs.
- `tests/test_spy_v103_multimonth_original_closedbar_orb.py` — real signed V55/V65 option quote integration fixture, missing source/nonzero cash, unresolved position, original-source SHA tamper, source-month mismatch, early-close exclusions, missing-month censorship, gzip immutability, synthetic end-to-end month runner.
- `scripts/run_spy_v103_multimonth_original_closedbar_orb_20261101.ps1` — compile + targeted regression gate then one **11-month** campaign.

### Boundaries

**Simulation research, not trading authorization.** The complete V55 quote tape contains observed BID/ASK candidates, not guaranteed executable fills at those prices. No original first publication time independent certification. V103 uses only historical original stock minutes/option quote archives and does not claim brokerage alpha. A month missing any essential original source is not a losing trade or a zero-return day. A monthly standalone $25,000 cash result does not establish a consecutive 11-month compounded account result if another month is censored. A fixed watch-list best-month retrospective selection is not valid independent OOS. Stop/target fills and intra-quote adverse selection remain modeling risks.

Next research decision after evidence: audit source complete vs absent months and actual historical trade counts; compare monthly/weekly V55 close P&L and downside concentration only over source-complete contiguous periods, not cherry-picked green months. If archive coverage is inadequate, build a source-demand plan for **specific newly identified query identities** under V38's no-repeat/no-ambiguous-retry policy; avoid re-acquiring same scopes or opening the protected 2026 master holdout. Independently test the V51 first-tick approach **only after** real tick-first crossing, as-of strike identity and original option source clocks can be established; don't equate V55 with the externally claimed result.
