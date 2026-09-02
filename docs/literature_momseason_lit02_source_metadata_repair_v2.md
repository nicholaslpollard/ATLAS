# LIT-02 source metadata repair v2

Authority: **EXPLORATORY / NON-AUTHORITATIVE**

This repair is a source-feasibility repair only. It does not authorize Phase33, economic testing, PAPER, LIVE, broker access, order writes, production behavior, or merge to main.

## Accepted base evidence

Repair-v2 is pinned to the accepted target-machine LIT-02 source census and diagnostic:

- source policy fingerprint: `4768ac204a68bbc7d89fa64c96574934d1e4149169cd6c222ef16be5bc1367ae`
- feasibility plan fingerprint: `c9200212a67171ee7c712a64224263241d622d2e8fe494ce0bc13843a8052880`
- v1 classification fingerprint: `636fb4bce1d5cd1501c535159e053dd39f5a301f9991b919b00ed2c8cc2e872c`
- v1 report fingerprint: `0f739c24013d6490e76c15461a1e5c69149fa09105b94c631f3e0a64fa43b2ca`
- diagnostic fingerprint: `6253178a77b26d5fa1ae9e99e5ff2036fab913ce9a5b3560a1989f6a6d1a3a2e`
- accepted cases: 199
- v1 resolved: 36
- v1 unresolved: 163
- v1 source coverage: 18.09%

The first-pass `development/l2/m/` evidence is immutable. Repair-v2 writes to `development/l2/m2/`.

## Why v2 exists

The accepted source-only diagnostic showed that the unresolved population is structured:

- Massive ticker-event source not found: 109 cases
- no admissible 8-K evidence: 70 cases
- terminal effective date with zero recognized matches: 66 cases
- no Composite FIGI: 47 cases
- terminal effective date with multiple recognized matches: 27 cases
- multiple terminal cash values: 23 cases
- two cases with a READY SEC candidate but another unresolved requirement

Those counts overlap. The repair is therefore mechanism-based rather than ticker-specific.

## Repair-v2 contract

Contract:

`lit02-source-metadata-repair-v2-contextual-sec-execution-370d-6k-no-prices`

The repair changes source interpretation only. It does not change the frozen return paths.

### 1. Retry only v1 unresolved cases

The 36 accepted v1 resolved cases are reused unchanged. Only the 163 v1 unresolved cases are eligible for repair-v2 source reads.

### 2. Preserve official-source authority

Repair-v2 uses official SEC current-report evidence and Massive only for permitted identity verification.

SEC forms admitted for source metadata:

- `8-K`
- `8-K/A`
- `6-K`
- `6-K/A`

Adding `6-K` supports foreign private issuers while preserving the frozen policy requirement for official SEC transaction/ticker-change evidence. A `6-K` is not sufficient merely because it exists; it must contain the same explicit executed transaction, ticker-continuity, or terminal-distribution facts required by the frozen path.

### 3. Bounded historical SEC search

The v1 62-day SEC lookback was too narrow for some stale-symbol / delayed-source cases. Repair-v2 uses a fixed 370-day lookback and the existing 10-day filing-forward allowance.

The forward allowance does not permit a future economic event: every classified effective date must still be on or before the frozen endpoint session.

Candidate filings are capped at 128 per lookup. Exceeding the cap fails closed.

### 4. Contextual executed-event parsing

V1 searched the complete submission globally for event dates and consideration values. That can produce either zero recognized closing dates or multiple unrelated cash values.

Repair-v2 first identifies bounded contexts containing explicit execution language such as:

- merger/transaction completed
- merger/transaction consummated
- merger/transaction closed
- merger became effective
- `On <date> ... merged with and into ...`

Consideration is then extracted from that executed-event context instead of choosing from arbitrary values elsewhere in the filing.

Strong common-share consideration phrases take precedence over generic per-share dollar references. This prevents option exercise prices, financing reference prices, convertible-note values, or earlier proposed terms from automatically becoming terminal common-share consideration.

### 5. Chronological precedence

A 370-day window can contain more than one legitimate corporate event. Repair-v2 therefore chooses only the latest admissible explicit effective event at or before the endpoint session.

If multiple incompatible classifications remain on the same latest effective date, the case fails closed.

### 6. Ticker-continuity expansion

Repair-v2 retains the v1 explicit `OLD -> NEW` parser and adds source patterns for SEC-filed notices that state a dated commencement under a new trading symbol while identifying the prior/present symbol.

A scheduled SEC notice alone does not finish the path. The existing endpoint identity verification must still confirm the successor ticker through Massive identity data.

## Target-machine transport interruption and repair

The first exact-head repair-v2 acquisition at `a0c9f9e9a46bd15296a87de203920105cdea74d8` reached case `131/199`. Case 131 (`2024-05-31 SCX`) completed as `RESOLVED / TERMINAL_CASH`; the following SEC complete-submission transfer then terminated mid-stream with `http.client.IncompleteRead` after 9,353,282 bytes.

This is a transport interruption, not a source classification or scientific-policy result. The interrupted HTTP body is not admissible evidence and must not be decoded, cached, or classified.

The shared SEC archive client already had a fixed three-attempt retry policy for retryable HTTP/URL/timeout failures. The transport repair adds `http.client.IncompleteRead` to that same bounded retry class. Each incomplete response is discarded in full and the complete GET is reissued from byte zero under the unchanged:

- SEC pacing/rate-limit policy;
- three-attempt maximum;
- exponential retry delay;
- default 20 MB submission ceiling;
- isolated scientific submission ceiling of 256 MB where explicitly requested.

`IncompleteRead.partial` is never accepted as a submission body and is never cached. Exhausting the existing attempt bound fails closed with `ProviderError`.

Repair-v2 per-case checkpoints under `development/l2/m2/` remain reusable. Resuming without `--force` validates and reuses completed manifests, so the target machine does not intentionally reacquire already completed repair-v2 cases.

No market-price/return, protected, broker, order, PAPER, or LIVE authority is added by this transport repair.

## Accepted target-machine repair-v2 result

Exact target-machine head:

`b51857461f7034591b32079ad126ea9c7ffa7310`

Accepted result:

- status: `LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE`
- feasibility cases: `199`
- base resolved: `36`
- base unresolved: `163`
- resolved after repair-v2: `96`
- newly resolved: `60`
- unresolved after repair-v2: `103`
- source coverage: `48.24%`
- required source coverage: `100%`
- path counts: `81 TERMINAL_CASH`, `15 TICKER_CONTINUITY`, `103 SOURCE_UNRESOLVED`
- source-metadata provider reads during resumed run: `481` (`0 Massive`, `481 SEC`)
- cached repair-v2 cases reused: `131`
- v1 resolved cases reused in the resumed tail: `14`
- v1 unresolved cases retried in the resumed tail: `54`
- economic outcome values read: `0`
- new price/return provider reads: `0`
- protected return rows read: `0`
- protected holdout consumed: `False`
- LIT-02 economic design unblocked: `False`
- Phase33 signal-to-trade authority: `False`
- classification fingerprint: `6d11081f7acf39783a9c6b2fde8119a1f19f9b8b3b87be0ab3fac59a8381faa2`
- report fingerprint: `dca474d2d88c09f904c33e33659fbb88e4cdadcecd9d40666971b4482a1c657e`

Residual unresolved reasons are overlapping:

- `TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED`: 79
- `MASSIVE_TICKER_EVENTS_NOT_FOUND`: 71
- `COMPOSITE_FIGI_UNAVAILABLE`: 25
- `TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED`: 25
- `NO_ADMISSIBLE_OFFICIAL_SEC_EVIDENCE_V2`: 15
- `MULTIPLE_TERMINAL_CASH_VALUES`: 10
- `SUCCESSOR_TICKER_IDENTITY_REQUIRED`: 4
- `MULTIPLE_SEC_READY_CLASSIFICATIONS_AT_LATEST_EFFECTIVE_DATE`: 1
- bounded candidate filing count exceeded (`146 > 128`): 1

This result is **not an economic alpha result**. It says only that the currently frozen/public-provider source stack still cannot classify every required missing-return stress case.

## Residual diagnostic gate

The next permitted action is a cached diagnostic over the accepted `m2` manifests. Its contract is:

`lit02-repair-v2-residual-diagnostic-v1-cached-m2-manifests-no-provider-reads`

The diagnostic is pinned to the accepted repair-v2 classification/report fingerprints and exact `96 / 103` counts. It performs no provider reads and no market-price/return reads. It separates residual mechanisms including:

- missing Composite FIGI / Massive event-source absence;
- SEC filing-candidate bound exhaustion;
- no admissible official SEC evidence;
- effective-date extraction gaps;
- execution-context gaps;
- terminal cash-value conflicts;
- successor-ticker identity requirements;
- latest-effective-date classification conflicts.

The diagnostic may support a subsequent general, prospectively declared source repair only if the residual evidence demonstrates a source mechanism that can be resolved without outcome-dependent or ticker-specific exceptions. Otherwise LIT-02 should close as source-infeasible.

## Prohibited behavior

Repair-v2 or its residual diagnostic may not:

- drop a frozen case or holding;
- zero-fill a missing return;
- substitute an arbitrary last traded price;
- infer merger consideration from price behavior;
- select a source rule using LIT-01 return sign or magnitude;
- create ticker-specific source exceptions;
- read new market-price or return outcomes;
- read the protected holdout;
- weaken the required 100% source coverage gate;
- reinterpret LIT-01 as economically positive or negative.

## Decision rule

- if source coverage reaches **100%** under a prospectively valid source contract, LIT-02 source feasibility is ready and a new fresh/non-reused economic-development design may be frozen before any economic outcome read;
- if source coverage remains below **100%**, economic testing remains blocked and the remaining cases must either receive another prospectively justified source-only mechanism repair or LIT-02 must close as source-infeasible.

No partial-portfolio economic test is permitted.
