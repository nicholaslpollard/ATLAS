# LIT-01 Development Source-Incomplete Diagnostic

Authority: **EXPLORATORY / NON-AUTHORITATIVE**.

This diagnostic exists only for a frozen LIT-01 development run that completed target acquisition but returned `LIT01_DEVELOPMENT_TARGET_SOURCE_INCOMPLETE`.

## Scientific meaning

`LIT01_DEVELOPMENT_TARGET_SOURCE_INCOMPLETE` is a source-integrity status, not an alpha rejection and not a successful alpha result. Confirmatory inference is withheld whenever any frozen holding lacks a valid prior or target endpoint required by the predeclared one-month total-return formula.

The diagnostic must not:

- change the frozen holdings or target-plan fingerprints;
- delete a holding because its return is unavailable;
- substitute a zero return;
- substitute an arbitrary last traded price;
- choose a repair based on the sign or magnitude of the strategy result;
- read the protected holdout;
- submit PAPER or LIVE orders.

Any later repair must be provider-grounded, outcome-sign-independent, and applicable prospectively to the same source condition.

## Diagnostic contract

`lit01-development-source-incomplete-diagnostic-v1-cached-target-manifests-no-provider-reads`

The diagnostic reads only already-frozen holdings, the frozen target plan, and completed local target acquisition manifests. It makes zero provider calls.

It reports:

- unavailable frozen target-plan rows;
- unique unavailable provider transport keys `(endpoint_session, historical_ticker)`;
- provider availability status counts;
- unique frozen holdings blocked by one or both required endpoints;
- blocked holdings by hypothesis and target month;
- for every unavailable provider key: endpoint date, ticker, stable instrument IDs, prior-endpoint hits, target-endpoint hits, affected hypotheses, and affected target months.

The distinction between frozen plan rows and provider transport keys is intentional. Multiple stable instrument identities can legitimately share one provider `(date, ticker)` observation at a corporate-action boundary. The diagnostic does not merge those instrument identities.

## Target-machine command

```powershell
git fetch origin
git switch literature-anchored-alpha-exploration
git pull --ff-only origin literature-anchored-alpha-exploration
git rev-parse HEAD

.\.venv\Scripts\python.exe scripts\diagnose_literature_momseason_development_source.py
```

The resulting JSON report is written beneath the existing frozen development directory as `development_source_incomplete_diagnostic.json`.

No acquisition flag is required because this step must not perform new provider reads.
