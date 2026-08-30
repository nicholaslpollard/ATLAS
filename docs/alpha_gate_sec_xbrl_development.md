# Pre-Phase33 SEC XBRL Fundamental Alpha — Development Evaluation

**Status: IMPLEMENTED / MARKET OUTCOMES NOT YET RUN ON TARGET MACHINE.**

This package is the first stage of the SEC XBRL fundamental-quality mechanism permitted to read market outcomes. It remains development-only. Protected returns remain sealed.

## Frozen lineage

Scientific contract: `alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Predictor contract: `alpha-gate-xbrl-predictor-v1-accession-pit-quarter-yoy-signals`

Development contract: `alpha-gate-xbrl-development-v1-63-session-spy-relative-protected-blind`

Outcome contract: `alpha-gate-xbrl-outcome-v1-exact-open-t63-close-spy-relative-split-censored`

Finalist artifact contract: `alpha-gate-xbrl-finalists-v1-selection-internal-protected-source-precheck-returns-unread`

Development implementation fingerprint: `3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

## Predictor reconstruction

The exact accepted 200-CIK feasibility sample is reused with no performance-based resampling. Company Facts remains the standardized XBRL source. SEC submissions metadata remains authoritative for exact accession, original 10-Q/10-K form, filing date, and acceptance time. Massive reference remains authoritative for exact historical `CIK + date + active=true + type=CS` security identity.

The normal development path batches SEC submissions reconciliation by issuer, so one root submissions document can resolve many accessions. This changes request efficiency only; it does not relax exact accession/date/form validation. A bounded per-accession fallback is used only if an issuer batch fails, and unresolved accessions remain excluded.

Quarterly facts are reconstructed point-in-time from the first accepted original filing for each issuer fiscal-year/fiscal-quarter pair. Later same-fiscal-period accessions do not overwrite the original PIT quarter state. Q2/Q3 YTD facts may be incrementalized only against already-public same-year YTD history, and Q4 may be reconstructed only as FY minus already-public PIT Q1/Q2/Q3 quarter values. Current filings do not rewrite prior-year feature values.

Identity is resolved once per issuer-quarter decision session and then shared by all frozen hypotheses emitted for that quarter. This prevents redundant Massive reads without changing the identity contract.

## Development-only market outcomes

Only rows with stage `DEVELOPMENT` are joined to daily market bars. The entry is the exact decision-session open and the primary exit is the exact close 63 XNYS sessions later. SPY uses the identical entry/exit sessions. Stock paths with missing exact entry/exit bars are censored. Paths crossing an accepted Massive split event are censored using the already-accepted Phase26 split evidence.

No protected predictor row is included in the market-price query. Protected predictors are allowed only for the later source-only sufficiency count.

## Selection and internal validation

Development calendar sessions are split chronologically 70/30 with an exact 63-session purge between selection and internal validation. Four contiguous selection folds and three contiguous internal-validation folds are fixed by calendar session, not by observed signal density.

For each of the six hypotheses, selection metrics are computed from session-aggregated outcomes. The frozen direction-specific primary and stress costs are applied. Hard gates include sample size, signal sessions, unique instruments, positive folds, positive primary mean, positive bootstrap lower confidence bound, positive stress mean, positive unhedged mean, year robustness, and session/instrument concentration.

The six selection p-values are adjusted globally by Holm–Bonferroni at alpha 0.05. A candidate can pass selection only if all hard gates pass and its Holm null is rejected.

At most one LONG and one SHORT selection winner can proceed. Winner ranking uses only the selection-tranche primary lower confidence bound, then candidate ID. Internal-validation metrics are not computed for candidate selection and cannot choose the winner. Internal validation only confirms or rejects the already-selected winner. Runner-up substitution is forbidden.

## Protected source-only precheck

Only internal finalists receive a protected predictor sufficiency check. This check reads no prices or returns. The frozen floors are:

- at least 75 protected predictor rows;
- at least 30 protected signal sessions;
- at least 25 protected unique instruments.

A finalist failing these source-only floors closes without spending the holdout. A finalist passing them becomes eligible for a later one-time protected return read. This development package itself always records:

- protected return rows read = 0;
- protected holdout consumed = false;
- Phase33 Signal-to-Trade authority = false;
- provider writes, broker reads/writes, order writes, PAPER, LIVE, and automation writes = 0.

A development result may therefore be `ACCEPTED_NEGATIVE_DEVELOPMENT`, `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`, or `DEVELOPMENT_PASS_FINALISTS_READY_PROTECTED`. None of these statuses by itself constitutes accepted `SUPPORTED` alpha.
