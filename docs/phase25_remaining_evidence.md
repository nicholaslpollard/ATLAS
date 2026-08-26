# Phase 25 — Remaining Cumulative Evidence Gates 8–11

**Status: IMPLEMENTED TOGETHER / PREREGISTERED BEFORE STRATEGY-RETURN TARGET EVIDENCE**

## Accepted Gate7 boundary

Accepted target-machine Gate7 evidence through **2026-08-21**:

- Gate6 WARM/HOT directional rows: **23,177**;
- exact PIT ticker intervals: **9,609**;
- ticker raw/persisted history rows: **5,392,759 / 5,392,759**;
- discovery direction: **16,079 bullish / 7,098 bearish**;
- market-compatible candidates: **17,285**;
- ticker-compatible candidates: **15,283**;
- fully route-eligible candidates: **15,283**;
- eligible route decisions: **61,132**;
- route decision rows: **185,416**;
- provider reads/writes: **0 / 0**;
- operational regime writes: **0**;
- broker/order/PAPER/LIVE/support activity: **0**;
- independent validation: **PASS**;
- Gate7 Pass: **true**.

Gate7 established the historical production-path population and exact market/ticker routing context without evaluating strategy rules or returns.

## Workflow change

Gates8–11 are deliberately implemented and preregistered as one coherent batch **before** any Phase25 production-path strategy-return evidence is inspected. This prevents threshold adaptation after seeing Gate8 results and removes unnecessary operator handoffs between evidence gates.

The cumulative target workflow is:

`Gate8 development attribution -> Gate9 robust selection/internal validation -> Gate10 finalist-only protected confirmation -> Gate11 cumulative diagnostic closeout`

The operator runs one cumulative command after exact-head cross-platform CI passes. Valid zero-selection, zero-finalist, or zero-confirmed outcomes continue through the remaining gates and are not treated as software failures.

---

## Gate8 — development-only incumbent attribution

Gate8 holds constant:

- all eight incumbent v1 strategy rules;
- the accepted `strategy-outcome-v1-direction-adjusted-three-session-return` outcome;
- the existing cost grid **0 / 5 / 10 / 25 bps**;
- the accepted Gate7 production StrategyRouter result;
- Phase11 support state.

Development evidence is restricted to:

- start: **2021-08-16**;
- end: the session immediately preceding the existing final holdout start;
- protected start: **2026-05-12**.

Gate8 cannot read protected strategy evidence.

For each incumbent it computes two side-by-side studies over the same development dates:

1. **broad comparator** — the accepted Phase11/24 research source and historical broad market routing;
2. **production path** — only Gate7 route-eligible rows joined by exact `(session_date, instrument_id, provider ticker)` identity, then the unchanged incumbent rule.

Gate8 also materializes the exact production-path rule-fired signal rows for Gate9.

### Research-source coverage is evidence

Gate8 does **not** assume that every Gate7 route row exists in the old Phase11/24 research source. It reports:

- development route-eligible rows;
- exact research-source matched route rows;
- unmatched route rows;
- exact coverage fraction.

Missing coverage is never silently guessed, backfilled from future metadata, or discarded from the diagnostic record. If coverage is incomplete, Gate11 carries that fact into the closeout.

Gate8 writes no support, provider, broker, PAPER, or LIVE state.

---

## Gate9 — preregistered robustness and internal validation

Gate9 reads only the Gate8 development signal artifact. It cannot read protected evidence.

The statistical machinery is intentionally inherited from the already accepted Phase24 challenger methodology rather than weakened for Phase25:

- primary cost: **10 bps**;
- stress cost: **25 bps**;
- selection fraction: **75%**;
- purge: **3 sessions**;
- selection folds: **6**, requiring at least **5 positive**;
- internal folds: **3**, requiring at least **2 positive**;
- circular/session block bootstrap: **6-session blocks**;
- bootstrap replicates: **2,000**;
- bootstrap seed family inherited from Phase24;
- selection confidence: **95%**;
- internal confidence: **90%**;
- selection minimum: **1,000 raw rows / 250 signal sessions**;
- internal minimum: **300 raw rows / 80 signal sessions**;
- positive primary mean;
- positive primary median;
- primary positive rate at least 50%;
- positive block-bootstrap lower confidence bound;
- positive 25-bps stress mean;
- year robustness at least 60% across eligible populated years;
- regime robustness at least 50% across eligible populated regimes;
- maximum single-session row concentration: 10%.

Because Phase25 tests exactly eight fixed incumbents rather than many variants within each family/direction, Gate9 uses a **global Holm-Bonferroni correction across all eight incumbents** at alpha 0.05. This is more conservative than treating each family/direction as an isolated one-test family.

Selection is hash-locked before internal validation. Internal failures do not fall back to another strategy.

Gate9 writes no support and grants no protected-evidence authority.

---

## Gate10 — finalist-only protected confirmation

Gate10 is the only remaining gate permitted to read the existing protected interval, and only after Gate9 has frozen its finalist list.

Hard behavior:

- zero Gate9 finalists -> **zero protected reads** and `SKIPPED_ZERO_FINALISTS`;
- nonzero finalists -> query only those exact finalists on Gate7 route-eligible rows;
- protected dates: **2026-05-12 through 2026-08-11**;
- folds: **3**, requiring at least **2 positive**;
- confidence: **80%**;
- minimum: **75 raw rows / 24 signal sessions**;
- primary/stress/median/positive-rate/LCB/concentration requirements remain in force.

The protected interval is explicitly classified **NON-FRESH** for support authority because the broader project has already inspected that time period in prior model/strategy work. It can confirm or contradict the new production-path filter, but it cannot by itself create production support.

Gate10 never writes Phase11 support.

---

## Gate11 — cumulative diagnostic closeout

Gate11 performs no new strategy-return reads. It synthesizes the validated Gates8–10 artifacts into one diagnostic row per incumbent containing:

- broad 10-bps row count and mean;
- production-path 10-bps row count and mean;
- broad-to-production mean delta;
- sign flip / improvement / worsening classification;
- selection check failures;
- Holm decision;
- internal validation failures;
- protected confirmation failures;
- selection/finalist/confirmed status.

It also aggregates failure counts across the entire strategy set so the next engineering/research change targets the dominant observed failure mode rather than weakening gates generically.

Possible closeout verdicts:

- `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`;
- `NO_SUPPORT_REPLACEMENT_PROTECTED_CONFIRMATION_FAILED`;
- `RESEARCH_CANDIDATES_REQUIRE_FUTURE_PROSPECTIVE_CONFIRMATION`.

Even the strongest third result leaves the Phase11 support map unchanged. Fresh future prospective evidence is required before any later phase can request support authority.

---

## Cumulative command contract

The single target command is:

`python scripts/run_phase25_cumulative.py --through 2026-08-21`

It sequentially runs Gate8 + independent validation, Gate9 + independent validation, Gate10 + independent validation, and Gate11 + independent validation.

There is no interactive confirmation because the remaining work is local research-only evidence processing. Gates8–11 make no provider calls and have no broker/order/PAPER/LIVE authority.

If an integrity or lineage error occurs, the cumulative runner stops and reports `BLOCKED`. Valid negative research outcomes continue to Gate11 and finish `COMPLETE`.

## Non-goals

Gates8–11 do not:

- invent or mutate strategy rules;
- change the three-session outcome;
- lower Phase24 robustness thresholds;
- fabricate sector history;
- issue provider reads or writes;
- read or mutate brokers;
- submit PAPER or LIVE orders;
- change Phase11 support;
- change ML authority;
- promote scheduler/PostgreSQL/browser execution authority.

The purpose is to finish the Phase25 route-fidelity experiment in one cumulative evidence pass and then make a targeted next decision from the complete diagnostics.
