# V98 — Source-first historical CALL union acquisition and original cache safety

**2026-11-01. Implementation committed; workstation execution pending. This is SOURCE-ONLY, NOT an options strategy simulator run or validation of a profitable rule.**

## Input evidence accepted

User ran V97B at pinned `8e03b84a797eeb74d03164a81a321f444c3f7a8a`, passed **23 tests**, saved `spy_v97b_49_variant_call_only_source_union_20261101_131407.zip`. Uploaded ZIP verified CRC PASS and all three canonical signed JSON+newline SHA roots:
- `summary.json`: `4f06bfebe52b1e0e4eeae35deea5305da25cac9c43ca2dc3d9809c7500e78217`;
- `call_only_candidate_source_coverage.json`: `49197acfc6aad240cdc0011197699ddf890ec3d7f0ab08a38957e52939300e1d`;
- `new_exact_call_source_union_preview.json`: `455bdd5d58452fd5e5d92f648353c413a9da2fa6e0164ffb0143606aa1eae37a`.

All parent links verified. Exact original counts 49 trial entry variants, 2,482 hypothetical candidate occurrences, 2,053 already archived original-source candidate occurrences, 426 candidate occurrences with 226 distinct candidate NEW exact source scopes, and 3 occurrences with 1 exact previous 2020 May ambiguous query that must NOT be automatically retried. All source records describe 0DTE SPY CALL rights; no option outcome or net PnL simulated by V97B.

Independent local canonical-check of this uploaded V97B source roster using original historical XNYS session closes reconstructed the full V38 `option_history_exact_quote_tape` request (symbol, session, expiry, strike, CALL, interval 1s, exact 09:35:01/09:40:01 source start, 15:30 or early close minus 55 minutes end). **All 2,056 archived + original-unknown source candidate occurrences matched the previously signed original V38 query ID** with 0 conflicts. All 226 new scopes produced 226 unique normalized exact query IDs; early-close examples 2018-11-23, 2024-07-03, 2025-07-03 require source cutoff 12:05 ET, not 15:30. This avoids assuming different query clocks or underlying prices were already sourced.

## New implemented V98 mechanism

`scripts/run_spy_v98_historical_call_union_safe_acquisition.py` verifies the original three V97B SHA roots and parent links. It checks exact 2053+3 old source candidate identities against fully normalized historical V38 provider query IDs, exactly 49 frozen entry variants, the 426 new occurrences and every 226 deduplicated original new requirement and interested variant. Any original provenance disagreement stops **before** output creation or new GET. Source plan cannot include the previously ambiguous May-2020 query.

Next, local original V38 SQLite source index is opened with **`mode=ro`** (no schema create or writes), checking each new request's original canonical request JSON and exact query identity. The output distinguishes:
- `ARCHIVED_SHA_VERIFIED`: _unpack rehashes original raw/gzip and verifies source integrity, no GET;
- `EXPLICIT_NO_DATA`: provider previously certified explicit no-data, no retry;
- `BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY`: `FAILED_RETRYABLE` or `IN_FLIGHT` even after timeout, no retry;
- `NOT_REGISTERED`: eligible for new first-time exact cache-first acquisition only.

Every planned 226 query must have **exactly one** read-only inspection result; missing/duplicate audit entries stop before GET. The entire audited source plan is written SHA-signed *before* any first-time provider GET. In `--acquire-new` mode, **ONLY NOT_REGISTERED** entries reach existing V39 `resolve_strategy_source_demands` with `continue_on_error=True`, which itself rechecks V38 prior status and does not retry ambiguous same query. A new event journal is append-only and SHA parent-linked, fsynced at every start/dispatch/done/blocked/failed event; signed completion reports preserve original V98 preflight ancestry, actual V39 provider attempt counts and cache/new source receipts, without copying entire option tapes into the evidence ZIP. Original source tape bytes are stored safely in the existing V38 compressed archive. Any source with ambiguous new dispatch is never automatically resubmitted.

`scripts/run_spy_v98_historical_call_source_union_acquisition_20261101.ps1`: pinned research branch, clean tracked working tree, Python compile, new V98 unit regressions + V97B/V97A/V89/V90/V38/V39 existing regressions; then original signed V97B input, read-only audit and new-only source acquisition in one command. Output `spy_v98_safe_call_source_acquisition_<stamp>.zip` preserved even if a source stage stops. Logs original source state counts, true provider dispatches, explicit no-data, ambiguous source counts, no broker orders.

All original stock decisions remain source-only. Historical same-day SPY options base-weekday listing calendar is a necessary **but NOT complete independent contract listing proof**. Alpaca news feature joins are not yet in the simulation. Some V89 as-of minute-bar timestamps are assumed to be available at +1 second and the gap prior-session close publication proof is limited; cannot assert actual historically executable fills. New 1-second option tapes enable **next** offline actual quote economics and shared-capital replay once source completeness passes; they do not themselves prove profitable paper/live strategies. The protected 2026 May–Aug master holdout remains sealed; 2020 source uncertainties remain censored.

## Next phase after V98

- Independently audit all V98 new quote cache receipts, source SHA/gzip, first-quote clock, bid/ask spreads and bid/ask size, missing prior source status. Distinguish true no-data from market-closed/contract not listed and from provider timeout. Do not automatically call an uncertain query again.
- Implement a **single causal CALL-only historical quote runner** that simulates the 49 preregistered entry configurations against the union of 351 previously available original and new first-time CALL contract tapes, linking source SHA to chronological 09:35/09:40 stock decision; 3 legacy exit policies × 2 lag × 4 rest (1,176 planned entry×execution definitions) may run offline **without re-downloading per policy**, with all outcomes and conflicts recorded.
- Join only SHA-verified news article-count metadata effective by each decision; 2018–2020 historical news unavailable, not zero-news. Historical text sentiment still unproven point-in-time.
- Preserve prior-only train/validate separation, multiple-testing correction and clear source/fill-vs-quote uncertainty. No strategy promotion or live order authorization.

## Workstation regression incident and correction — 2026-11-01

The user's initial pinned V98 run at `ff2bc5a5acdae45d1f8af514b68831b254831c0b` compiled successfully and then stopped at the **pre-acquisition pytest gate**: **41 tests passed, one failed**, `test_sqlite_source_index_read_only_unknown_and_no_data`, `KeyError: 'session'`. No ThetaData GET, no source dispatch, no broker orders, and no V98 paid acquisition evidence ZIP were created. The test built a **normalized provider requirement** from `build_requirement(preview(...))` and incorrectly supplied it directly to `read_only_v38_state`, whose actual original full source-union caller passes `{**historical_source_plan,**normalized_requirement}`; therefore the fixture omitted `session`, `decision_clock_et`, `strike`, `strategy_variants`. This is a test input contract defect, not evidence of bad historical source or a new V38 provider failure. The original original source cache is unmodified.

Revised the original SQLite test to use the exact runtime shape for four cached statuses and a fifth not-registered query, with the historical source-plan fields retained. Added assertions for original session ordering, CALL-only right/strike, variant lineage and no automatic query retry. Other V98 acquisition code and source/strategy behavior remain **unchanged**. All 42 tests are expected to run at the next workstation test gate; **this revision is not yet workstation verified**. Do not bypass tests or replay an ambiguous source to make a failing test green.
