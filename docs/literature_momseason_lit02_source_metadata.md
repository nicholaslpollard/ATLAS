# LIT-02 MomSeason — source metadata acquisition and classification

## Purpose

The accepted LIT-02 source-feasibility freeze contains exactly 199 source-missing stress cases from LIT-01. Its source-policy fingerprint is `4768ac204a68bbc7d89fa64c96574934d1e4149169cd6c222ef16be5bc1367ae`; its feasibility-plan fingerprint is `c9200212a67171ee7c712a64224263241d622d2e8fe494ce0bc13843a8052880`.

This stage acquires only the identity/corporate-action evidence needed to determine whether each frozen case has an admissible LIT-02 return path. It does **not** read Alpaca market prices, calculate returns, open the protected holdout, or grant Phase33/PAPER/LIVE/production authority.

Authority remains **EXPLORATORY / NON-AUTHORITATIVE**.

## Frozen acquisition contract

Contract:

`lit02-source-metadata-classification-v1-frozen-plan-massive-figi-sec-8k-no-prices`

The acquisition methodology is fixed before these source reads:

1. Reuse the accepted LIT-01 historical reference snapshots locally to recover source-safe stable identity metadata for the frozen instrument IDs.
2. If one authoritative Composite FIGI exists, query Massive ticker events. A unique ticker event valid on or before the frozen endpoint can establish `TICKER_CONTINUITY`.
3. If continuity is not established, use the unique authoritative SEC CIK when available.
4. Search a bounded SEC filing window from 62 calendar days before through 10 calendar days after the frozen endpoint. A post-endpoint filing may be used only as documentary evidence for a transaction/ticker event whose explicit effective/closing date is on or before the frozen endpoint.
5. Only original/amended `8-K` evidence is scanned in this first metadata family, limited to Items `2.01`, `3.01`, `5.03`, `8.01` when item metadata is present. Maximum candidate filings per CIK/case: 24.
6. SEC complete submissions use the already-established bounded scientific archive ceiling of 256,000,000 bytes. Global/default SEC archive limits are not changed.
7. Every case is checkpointed independently under the compact Windows-safe `development/l2/m/` namespace. A rerun reuses valid checkpoints unless `--force` is explicitly supplied.

## Admissible classifications in this source family

### `TICKER_CONTINUITY`

Accepted only when either:

- Massive Composite-FIGI ticker events establish a unique successor ticker valid at the frozen endpoint; or
- an official SEC filing explicitly states the old-to-new ticker-symbol change and effective date, and Massive endpoint reference metadata independently shows successor identity consistency through matching Composite FIGI or CIK.

### `TERMINAL_CASH`

Accepted only when the SEC filing provides:

- an explicit completed/consummated/closed transaction date on or before the frozen endpoint; and
- explicit per-share cash consideration tied to the executed transaction.

### `TERMINAL_STOCK`

Requires an explicit transaction date, exchange ratio, explicit successor ticker in the SEC filing, and authoritative Massive successor identity metadata. If successor identity is not explicit, the case remains unresolved.

### `TERMINAL_MIXED`

Requires the same evidence as `TERMINAL_STOCK` plus explicit per-share cash consideration.

### `TERMINAL_DISTRIBUTION`

Requires an explicit terminal/liquidating per-share distribution and explicit terminal transaction/effective date.

Anything contradictory or incomplete is `SOURCE_UNRESOLVED`.

## Important outcome boundary

SEC transaction consideration, exchange ratios, effective dates, and ticker-change facts are treated here as **source/transaction metadata required to classify the frozen return path**. They are not combined with a starting price and no return is computed during this gate.

Accordingly:

- `new_price_or_return_provider_reads = 0`;
- no Alpaca endpoint is called;
- no portfolio or signal performance is calculated;
- no protected return is read;
- no previously opened LIT-01 return sign or magnitude is used to choose a source rule.

The report retains the existing `economic_outcome_values_read = 0` safety field to mean that no market-price/return outcome vector is opened in this stage. Transaction-document metadata can be present in the evidence manifests because it is the source feasibility object being tested.

## Coverage rule

The accepted policy requires **100% admissible source coverage** across all 199 cases.

- 199/199 resolved: `LIT02_DELISTING_AWARE_SOURCE_COVERAGE_READY`. This only unblocks preparation of a separately frozen LIT-02 economic-development design; it does not itself authorize economic reads.
- Anything below 199/199: `LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE`. Economic testing remains blocked. Unresolved reasons must be diagnosed source-only.

## Live progress and restart behavior

The acquisition runner prints live case progress with completed/total, percent, elapsed time, ETA, current endpoint/ticker, cache/source mode, classification status, return path, and cumulative source-provider reads.

The identity scan also prints local snapshot progress. Once built, its compact identity cache is reused.

Each completed case is atomically checkpointed. If a provider or transport failure stops a long run, rerun the same command; valid completed cases are reused automatically.

## Command

```powershell
git fetch origin
git switch literature-anchored-alpha-exploration
git pull --ff-only origin literature-anchored-alpha-exploration
git rev-parse HEAD

.\.venv\Scripts\python.exe scripts\run_literature_momseason_lit02_source_metadata.py --acquire
```

Do not use `--force` for an ordinary retry. `--force` intentionally re-reads/reclassifies every case under the same frozen source contract and is reserved for a specifically justified cache rebuild.
