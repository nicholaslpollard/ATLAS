# ATLAS V97B — 49 causal CALL-only entry variants and deduplicated source union

**2026-11-01. Exploratory SOURCE-PREVIEW ONLY. Do not confuse this document with a historical PnL backtest.**

## Original V97A evidence

V97A user workstation run at pinned `e9c1d13bb8792c199b83612d773c4be061f1573e`: **24 regression tests passed**, all nine 2018–2026 Jan–Apr historical source cohorts reconciled, 11,826 original 6-family considerations, 376 archived CALL source receipts, 1 original May 1 2020 source-unknown CALL, 334 PUT requirements excluded, no provider/broker calls. Signed `summary.json` fingerprint **f587e8c536eb5730a81a1ccdae4f22a5d7ee723221b04d1377d63b07dc797e51**; original all-decisions source fingerprint **158eef47f0c9e7c2bbf4e013b46f72112af3d73eba64057557870feb814b9070**. Independent direct ZIP CRC and both compact canonical JSON+newline SHA signatures PASS. The 376 archived original CALL candidate **receipts represent 351 distinct original query IDs**, because multiple strategies occasionally used the same exact source scope. Original 2020 full-year outcome remains censored.

Original source rows: 10,798 NO_SIGNAL; 300 historically same-day 0DTE listing exclusions; 17 SOURCE_UNQUALIFIED_NO_TRADE with absent prior bars and original null decision; 376 archived CALL; 334 PUT excluded; one CALL unknown = 11,826. Some original feature-context news period within 2021+ was marked *awaiting source verification*, not as-of joined; 2018–2020 news history unavailable in currently qualified corpus.

## New V97B implemented preflight

New `scripts/run_spy_v97b_49_variant_call_source_union_preview.py` reads only V97A's two original signed JSON roots, **not** historical option quote outcome journals, price exits, or V95 profit rankings. Requires the pinned historical input population (11,826; 376 original CALL complete; one missing and 334 PUT excluded). Recomputes **all six original V89 fixed bullish decisions exactly** from the saved closed-minute original stock features: fails closed if even one originally recorded CALL condition does not reproduce. Applies the historical conservative SPY 0DTE weekly listing calendar to every tuned proposal, and preserves all original no-source dates.

The registered entry-only **49-variant grid**:
- `impulse_0935`: first-leg upward threshold 0.12, 0.16, 0.20, 0.25 percent (4).
- `acceleration_0940`: 3×3 first-leg and second-leg thresholds, with existing second-leg acceleration condition unchanged (9).
- `early_reversal_0940`: 3×3 negative first-leg and positive second-leg recovery thresholds (9).
- `pullback_resume_0940`: **9 strictly tightening subset filters on already-original CALLs**. V97A stock-feature export lacks the original final 09:39 minute candle direction, so it is **not scientifically valid to loosen and invent unseen original CALL entries**. Changed contracts beyond this subset must wait for the native 1-minute bars to be re-read and requalified.
- `gap_followthrough_0940`: 3×3 positive prior gap and first-ten-minute follow-through thresholds (9); each potential CALL explicitly flagged **PRIOR_CLOSE_PUBLICATION_NOT_INDEPENDENTLY_PROVEN** because original V89 feature metadata admits this uncertainty. No live-ready claim.
- `compression_release_0940`: 3×3 contracted second-range threshold and close-at-high location threshold, unchanged last price above first opening precondition (9).

For each original decision+variant, log no decision / unavailable historical listing / no bullish signal, or construct hypothetical same-day long SPY CALL from original as-of latest completed close rounded to nearest dollar. Match an existing source **only** on date, exact original decision second (09:35:01 or 09:40:01), 0DTE expiry, rounded strike and CALL right. Different-family same source scope is reused. A 09:35 tape possibly covering a 09:40 clock is NOT assumed reusable without physical original V38 start/end check; new source scopes are preview-only. Ambiguous original May-01 query cannot be added to any acquisition queue or automatically retried. Never create actual V38 normalized query, invoke SDK or open brokerage. Original V97A 11,826 source-decisions remains SHA-linked. All first-time candidate variants plus missing outcomes remain retained.

### Independently prototyped results on supplied signed V97A archive

The prototype was run locally on the exact uploaded V97A signed reports, and the original frozen bullish signal classifier matched **all 11,826 original considerations where the prior source was qualified**.

| Preview metric | Count |
|---|---:|
| Preregistered independent entry-threshold variants | **49** |
| Historical potential CALL candidate occurrences across grid | **2,482** |
| Candidate occurrences covered by original archived exact CALL tape | **2,053** |
| Candidate occurrences needing genuinely new source scope | **426** |
| Candidate occurrences tied to original known-unknown source | **3** |
| Distinct original already-archived exact CALL source scopes | **351** |
| Distinct NEW potential CALL scopes to review before GET | **226** |
| Distinct original ambiguous CALL scope to NEVER auto-retry | **1** |
| Variants × existing 24 quote-exit sensitivity settings | **1,176 potential scenario definitions, NOT simulated** |
| Historical PnL calculated | **NONE** |
| Provider and broker requests | **ZERO** |

Why 226 and not an earlier informal approximation of 227? The total absent-exact-original-source scopes is 227, but one is the **known ambiguous May 1 2020 source**, expressly NOT a fresh safe request. Thus 226 are unqualified NEW scopes, and 1 remains an unresolved previous dispatch. The **426** new candidate occurrences are not 426 separate provider calls; they deduplicate to 226 distinct identities. The original 2,053 occurrences can be evaluated offline only after linking their source tape to a historical account/execution adapter and validating original quote marketability. Source available does NOT imply a trade or profitable performance.

**Evidence output:** signed `call_only_candidate_source_coverage.json` with all original causal decision/source SHA, scenario ID, date/strike/action clock and missing/archived/ambiguous states; signed `new_exact_call_source_union_preview.json` with 226 de-duplicated *preview-only* 0DTE SPY CALL source identities and interested trial IDs, `summary.json` SHA links; protected 2026 May–Aug holdout sealed. Combined portfolio choices, historical news counts and outcome PnL are **NOT** yet executable. No result-driven parameter selection is performed. Comparisons across earlier opened historical periods are discovery, not a fresh holdout.

The GitHub source implementation is `scripts/run_spy_v97b_49_variant_call_source_union_preview.py`; five isolated original-source preview unit tests in `tests/test_spy_v97b_49_variant_call_source_union_preview.py` were run successfully in the assistant's local environment before GitHub publication; workstation code/test execution remains pending. `scripts/run_spy_v97b_49_variant_source_union_20261101.ps1` compiles, runs regression tests, executes all 49 trials offline and preserves output ZIP in finally. No PnL stage and no paid calls. Original V97A reports remain unchanged.

## Next source-and-simulator phase

1. Audit **226 new source scopes** in one batch against the original local V38 SQLite registry **read-only**, original archived historical tapes, and exact original provider request scopes before GET. A source may already be in cache under another existing query; do not assume 226 paid GETs. Never retry the one 2020 previous-dispatch-unknown source automatically. Verify minute-and-exchange listing/early close/expiry on each distinct date. If truly missing, acquire each unique normalized source **once** with append-only provider dispatch and SHA archive; preserve all missing/failed.
2. Independently bring in 2021+ source-integrity qualified **as-of Alpaca news metadata**, with 2018–2020 unavailable rather than zero; positive/negative text sentiment remains BLOCKED without original revisions.
3. Run original 1-second exact CALL quote tapes for the qualified source-union, with original time-causal entry, size and marketability, historical fees, original limits/latency, stop/target/runner/cutoff risk parameters, and all no-trades. Need a new chronological combined-capital engine that uses earlier-known positions/scores and cleanly distinguishes unfilled orders from modeled BID reference fills.
4. Preregister thousands of complete scenario specifications *without an unbounded combinatorial optimizer*; keep prior-fold selection and prospective validation requirements. Existing V95 eight-period negative study remains a baseline; an observed profitable post-hoc 49-grid variant is discovery only, not proof.
