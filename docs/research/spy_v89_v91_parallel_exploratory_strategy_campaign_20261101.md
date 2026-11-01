# ATLAS V89–V91 — Six NEW causal opening hypotheses; 2024–2026 comparative batch

**Registered:** 2026-11-01 BEFORE viewing any V89 option-trading outcomes.

## Why
Original V83 ORB continuation, failed-breakout fade and gap fade failed cross-regime reproducibility in the source-linked 2024 full-year V88 test (all three negative, combined negative; none of 92 complete considered existing exit/latency variants positive across all three cohorts). Do NOT tune or resurrect them by altering a rest window, deleting bad months, using later option quotes for entry, or misclassifying BID references as broker fills. These six are *new proposed opening-price hypotheses*, NOT research claims or predictions of profitability.

## Frozen cohorts and evaluation boundary

All six registered BEFORE data outcome inspection. Evaluate the **exact same source-first rules, strikes, risk policy and cash restrictions** in all cohorts without changing a threshold after seeing P&L:

| Cohort | Period | Data interpretation |
| --- | --- | --- |
| 2024_full | 2024-01-01..2024-12-31 | Full-year exploratory regime challenge |
| 2025_h2 | 2025-07-01..2025-12-31 | Comparison period, already studied for older hypotheses; NOT independent untouched holdout |
| 2026_janapr | 2026-01-01..2026-04-30 | Later comparison, already studied for older hypotheses; NOT independent untouched holdout |

The protected **2026-05-12..2026-08-11 master holdout remains SEALED**. All 18 family-by-cohort evaluations (6 × 3) and 504 quote-capital configurations are **exploratory**, even if an apparently successful variant emerges, because testing 24 correlated exit-policy variations and examining earlier published outcomes creates multiple-testing and researcher discretion risks. A new untouched forward/holdout validation, modeled costs and order fill proof are required before any strategy promotion.

## Six distinct causal entry hypotheses

Each uses exactly source SHA-confirmed SPY 1-minute original Alpaca SIP OHLC bars, with close-bar availability **at +1 minute**. A 09:35:01 decision sees only 09:30–09:34 bars; a 09:40:01 decision sees only 09:30–09:39 bars. No intraminute breakout assumption. Every day × family, including NO_SIGNAL and source failures, is recorded and signed.

1. **`impulse_0935`**: First five-minute closing-price change vs 09:30 open ≥+0.16% CALL or ≤−0.16% PUT. Direct opening directional impulse.
2. **`acceleration_0940`**: Same-signed first and second five-minute legs, first ≥0.08% and second ≥0.09%, second absolute movement at least as large as the first. CALL/PUT in direction of acceleration.
3. **`early_reversal_0940`**: First five-minute leg absolute ≥0.18%, second closes ≥0.13% in opposite direction. Contrarian CALL after opening drop or PUT after opening rally.
4. **`pullback_resume_0940`**: First leg absolute ≥0.20%, subsequent close retraces 25%–70% of the first impulse, last 09:39 one-minute candle closes back in the original trend direction. CALL/PUT with first-leg direction.
5. **`gap_followthrough_0940`**: The prior real exchange session's verified last regular stock bar is available before decision; 09:30 open gap ≥+0.45% or ≤−0.45% and first-ten-minute close advances ≥+0.08% or ≤−0.08% from today's open in gap direction. This is gap-continuation, the opposite thesis to the rejected V83 gap fade. Prior bar provider *publication proof* is not independently established and flagged.
6. **`compression_release_0940`**: The 09:35–09:39 observed range ≤55% of the first-five-minute range, 09:39 close in outermost top/bottom 20% of the total ten-minute price range, close also on the corresponding side of today's open. CALL/PUT for possible range expansion following compression.

These are **hypotheses chosen for diversity, not proven economic edges**. Overlapping signals may target the same contract, but each has a distinct signed candidate ID and must compete for one available account slot. No future prices or option quotes can decide whether to generate a source demand.

## Exact option source and execution settings

- For each qualifying causal stock signal, select original contemporaneous last completed stock close rounded to whole-dollar SPY ATM strike (round-half-up). Same-day expiration, CALL or PUT direction from the new stock-only signal. Selection timestamp is one second before registered decision; **no independent historical listing or liquidity proven** until quote tape is checked.
- V39 read-through *only* through the existing immutable V38 cache. On a cache miss new ThetaData 1-second option exact-contract tape may be fetched; archive all original results/receipts to the designated external storage. Provider dispatch is one serialized shared coordinator to avoid racing its persistent SQLite cache; all six strategies are discovered from a single original stock-source pass. A request's ambiguous/unknown prior dispatch does **not** trigger an unsafe duplicate retry.
- Freeze existing V84 entry discovery ≤10s after decision; modeled action quote after 1s OR 3s lag, up to 3s allowed quote slack, reject >1% adverse ASK drift, max four contracts and $500 original premium, $0.65 per contract per side, original spread/size quality gates. Three original V84 exit policies `control_50_100`, `balanced_35_100`, `runner_35_150` are **correlated sensitivity variants**, not three independent discoveries.
- Freeze V86 original fixed sell limit observation and resting windows **0/3/10/30s**, hypothetical cancellation/repricing after original lag if unmarketable, measured original **2% adverse exit BID** haircut. A quote at or above the original limit suggests marketability, NOT fill proof. Never treat failed-original-limit exits as zero loss or instant cash release.
- Original one-slot $25,000 notional research portfolio, deterministic entry **action-time** ordering and family registration tiebreak; if position is busy, log all declined simultaneous signal decisions. Option returns remain historical **quote-only hypothetical references**.
- For each cohort V90 builds 24 variants for **each exact option source** (3 policies × 2 delays × 4 original limit rests), with original full V84 event trail + V86 order event trail embedded in each gzip signed evidence journal. Builds 24 cash ledgers each for 6 single-family portfolios + one combined all-family portfolio: **168 signed portfolio ledgers per cohort**.
- All three cohorts give **504 portfolio comparison rows** in a signed V91 JSON matrix plus CSV, after checking 3 signed original V89 campaign roots, 3 V90 outcome report roots, all per-cohort summary/report parent links, and every 168 embedded portfolio SHA signatures.

## Exact saved evidence and failure rules

**V89 cohort directory:**
- `entry_screen.json`: every market session × all six families, source SHA, preregistered feature values, signal decision or no-signal and reason, per-cohort original source month SHA, stock-data failures, registry SHA.
- `exact_option_source_plan.json`: every signed requested exact option contract and decision provenance, including returned V38 query ID.
- `source_events.jsonl`: each provider cache-lookup/source event fsynced into append-only ordered signed SHA chain, including source ID, terminal source state and nonsecret failure type, to preserve partial campaigns during interruption.
- `source_receipts.json`: signed exact original V39 provider/cache receipts, source SHA and original request identity, last append-only event SHA.
- `summary.json`: all family denominators, source state, broker calls 0, master holdout nonaccess.
- Original FULL option quote rows remain in original source SHA immutable **V38 external cache**, not ZIP-duplicated in each report.

**V90 cohort directory:**
- `journals/*.json.gz`: one immutable deterministic gzip archive per exact-option demand × one 24 exit variant, containing the original SHA-bound V84 entry+exit decision and V86 original resting-limit recheck, observations, rejection reasons, source quote SHA, and both original signed report fingerprints.
- `trial_manifest.json`: complete journal census, SHA-256 of every compressed file, identity, status, event and quote-price lineage, original source and demand SHA references.
- `portfolio_ledgers.json`: all 168 fully signed cash ledgers with considered signals, rejected entries, busy-slot conflicts, hypothetical debits/credits, chronological release, monthly/weekly outcomes, worst completed-trade cash drawdown, top-two favorable quote contribution, true unresolved terminal position status. Unknown option expiry/exercise value is NEVER assumed zero.
- `summary.json`: all source/trial/ledger SHA roots, scenario totals, *unknown/uncensored* count, zero broker/provider calls.

**V91 matrix directory:** `full_matrix.json` (signed 504 rows), `full_matrix.csv` (CSV SHA preserved in signed summary), `summary.json` (signed source-parent roots, incomplete/complete cash flags, positive-three-cohort diagnostics). This matrix is a diagnostic, **not an automatic winner selector**.

## Gates

- Fail before any option GET if original stock source SHA or causally required minute geometry is invalid; store a rejected reason instead of silently repairing.
- No original 2026 May–August protected minute partition may be enumerated or opened. Freeze module `B34_MAX_SAMPLE_DATE=2026-04-30`.
- No future option BID or option profit may enter the stock-only discovery/contract choice. Do not silently select only historically closed exits for shared account.
- Do not promote strategies solely on cumulative positive results, especially if top-two wins dominate net profit or one period is negative. Respect 2024/2025/2026 differences, reported rejections, latency, quote marketability and fill/assignment limitations.
- Reuse exact original immutable source cache. All new quote GETs require the user executing the V89 batch on the local workstation; neither ChatGPT nor this repo can silently access local provider accounts.
