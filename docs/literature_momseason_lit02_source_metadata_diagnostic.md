# LIT-02 MomSeason — unresolved source metadata diagnostic

## Purpose

The accepted first-pass LIT-02 source-metadata census completed all 199 frozen feasibility cases without reading market-price/return outcomes or the protected holdout. It resolved 36 cases and left 163 `SOURCE_UNRESOLVED`, so the 100% source-coverage gate remains blocked.

Accepted target-machine source census:

- source policy fingerprint: `4768ac204a68bbc7d89fa64c96574934d1e4149169cd6c222ef16be5bc1367ae`;
- feasibility plan fingerprint: `c9200212a67171ee7c712a64224263241d622d2e8fe494ce0bc13843a8052880`;
- classification fingerprint: `636fb4bce1d5cd1501c535159e053dd39f5a301f9991b919b00ed2c8cc2e872c`;
- source report fingerprint: `0f739c24013d6490e76c15461a1e5c69149fa09105b94c631f3e0a64fa43b2ca`;
- resolved: 36/199;
- unresolved: 163/199;
- source coverage: 18.09%;
- resolved paths: 21 `TERMINAL_CASH`, 15 `TICKER_CONTINUITY`;
- economic outcome values read: 0;
- new price/return provider reads: 0;
- protected return rows read: 0;
- protected holdout consumed: false.

The unresolved reason counts overlap. They therefore cannot be interpreted as 163 mutually exclusive failures.

## Diagnostic contract

`lit02-source-metadata-unresolved-diagnostic-v1-cached-manifests-no-provider-reads`

The diagnostic is local and read-only with respect to external sources. It loads the accepted `development/l2/m/r.json` census plus all 199 cached per-case source manifests and first reconstructs the accepted classification fingerprint. If the cached population does not exactly reproduce `636fb4bc...`, the diagnostic fails closed.

It then reports:

- individual unresolved-reason counts;
- exact reason-combination counts;
- pairwise reason intersections;
- source-mechanism counts;
- SEC evidence modes;
- whether terminal-date failures contain zero or multiple explicit event-date matches;
- whether cash-value conflicts contain multiple candidate consideration values;
- Composite-FIGI/CIK availability intersections;
- Massive 404 overlap with SEC-capable identities;
- repeated unresolved tickers across endpoints;
- per-case source-only evidence summaries.

The complete per-case detail is retained in compact `development/l2/m/d.json`. The console runner prints only summary counts.

## Why this diagnostic comes before another repair

The first-pass source report contains several high-frequency reasons:

- `MASSIVE_TICKER_EVENTS_NOT_FOUND`: 109;
- `TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED`: 80;
- `NO_ADMISSIBLE_SEC_8K_EVIDENCE`: 70;
- `COMPOSITE_FIGI_UNAVAILABLE`: 47;
- `MULTIPLE_TERMINAL_CASH_VALUES`: 23.

Because reasons overlap, changing one parser or source rule before measuring intersections could obscure the actual root mechanism. In particular, a Massive ticker-events 404 is only an unavailable optional continuity source; cases with an authoritative CIK can still have usable SEC evidence. Conversely, effective-date and cash-value conflicts may be parser-scope problems, true documentary ambiguity, or both.

The diagnostic distinguishes those mechanisms without re-reading SEC/Massive and without opening any economic outcome.

## Safety invariants

The diagnostic must report:

- `provider_reads_performed = 0`;
- `economic_outcome_values_read = 0`;
- `new_price_or_return_provider_reads = 0`;
- `protected_return_rows_read = 0`;
- `protected_holdout_consumed = False`;
- `lit02_economic_design_unblocked = False`;
- `phase33_signal_to_trade_authority = False`.

It cannot weaken the frozen 100% source-coverage requirement or reclassify any case. It only analyzes the already-cached first-pass evidence.

## Command

```powershell
git fetch origin
git switch literature-anchored-alpha-exploration
git pull --ff-only origin literature-anchored-alpha-exploration
git rev-parse HEAD

.\.venv\Scripts\python.exe scripts\diagnose_literature_momseason_lit02_source_metadata.py
```

No `--acquire` or `--force` option is used because this stage performs no provider reads.
