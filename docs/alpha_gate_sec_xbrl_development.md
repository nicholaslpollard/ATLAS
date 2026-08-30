# Pre-Phase33 SEC XBRL Fundamental Alpha — Development Evaluation

**Status: TARGET DEVELOPMENT `ACCEPTED_NEGATIVE_DEVELOPMENT`; negative closeout PASS; protected returns remain unread.**

This package is the first stage of the SEC XBRL fundamental-quality mechanism permitted to read market outcomes. It remained development-only throughout. Protected returns were never opened.

## Frozen lineage

Scientific contract: `alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Predictor contract: `alpha-gate-xbrl-predictor-v1-accession-pit-quarter-yoy-signals`

Development contract: `alpha-gate-xbrl-development-v1-63-session-spy-relative-protected-blind`

Outcome contract: `alpha-gate-xbrl-outcome-v1-exact-open-t63-close-spy-relative-split-censored`

Finalist artifact contract: `alpha-gate-xbrl-finalists-v1-selection-internal-protected-source-precheck-returns-unread`

Development implementation fingerprint: `3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

## Predictor reconstruction

The exact accepted 200-CIK feasibility sample was reused with no performance-based resampling. Company Facts remained the standardized XBRL source. SEC submissions metadata remained authoritative for exact accession, original 10-Q/10-K form, filing date, and acceptance time. Massive reference remained authoritative for exact historical `CIK + date + active=true + type=CS` security identity.

The normal development path batches SEC submissions reconciliation by issuer, so one root submissions document can resolve many accessions. This changes request efficiency only; it does not relax exact accession/date/form validation. A bounded per-accession fallback is used only if an issuer batch fails, and unresolved accessions remain excluded.

Quarterly facts are reconstructed point-in-time from the first accepted original filing for each issuer fiscal-year/fiscal-quarter pair. Later same-fiscal-period accessions do not overwrite the original PIT quarter state. Q2/Q3 YTD facts may be incrementalized only against already-public same-year YTD history, and Q4 may be reconstructed only as FY minus already-public PIT Q1/Q2/Q3 quarter values. Current filings do not rewrite prior-year feature values.

Identity is resolved once per issuer-quarter decision session and then shared by all frozen hypotheses emitted for that quarter. This prevents redundant Massive reads without changing the identity contract.

## Development-only market outcomes

Only rows with stage `DEVELOPMENT` were joined to daily market bars. Entry was the exact decision-session open and primary exit the exact close 63 XNYS sessions later. SPY used the identical entry/exit sessions. Stock paths with missing exact entry/exit bars were censored. Paths crossing an accepted Massive split event were censored using the already-accepted Phase26 split evidence.

No protected predictor row was included in the market-price query. Protected predictors were allowed only for source-only sufficiency counts after an internal finalist existed.

## Selection and internal validation

Development calendar sessions were split chronologically 70/30 with an exact 63-session purge between selection and internal validation. Four contiguous selection folds and three contiguous internal-validation folds were fixed by calendar session, not by observed signal density.

For each of the six hypotheses, selection metrics were computed from session-aggregated outcomes. The frozen direction-specific primary and stress costs were applied. Hard gates included sample size, signal sessions, unique instruments, positive folds, positive primary mean, positive bootstrap lower confidence bound, positive stress mean, positive unhedged mean, year robustness, and session/instrument concentration.

The six selection p-values were adjusted globally by Holm–Bonferroni at alpha 0.05. A candidate could pass selection only if all hard gates passed and its Holm null was rejected.

At most one LONG and one SHORT selection winner could proceed. Winner ranking used only the selection-tranche primary lower confidence bound, then candidate ID. Internal-validation metrics could not choose the winner. Internal validation only confirmed or rejected an already-selected winner. Runner-up substitution was forbidden.

## Protected source-only precheck

Only internal finalists could receive a protected predictor sufficiency check. This check reads no prices or returns. Frozen floors were:

- at least 75 protected predictor rows;
- at least 30 protected signal sessions;
- at least 25 protected unique instruments.

A finalist failing these source-only floors would close without spending the holdout. A finalist passing them would become eligible for a later one-time protected return read.

## Accepted target-machine development result

Target development head:

`58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`

Result: **`ACCEPTED_NEGATIVE_DEVELOPMENT`**.

Accepted evidence:

- source-only predictor reconstruction: PASS;
- predictor rows: **5,536**;
- development predictor rows: **4,157**;
- protected predictor rows: **1,379**;
- usable development outcome rows: **3,963**;
- missing exact stock paths censored: **123**;
- split-crossing paths censored: **71**;
- development sessions: **850**;
- selection sessions: **595**;
- 63-session purge: `2023-12-27..2024-03-27`;
- internal-validation sessions: **192**;
- Selection passers: **0**;
- selection winners: **0**;
- Internal finalists: **0**;
- protected source-only prechecks: **0**;
- protected-return eligible finalists: **0**;
- Protected return rows read: **0**;
- Protected holdout consumed: **false**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: **0**;
- Phase33 authority: **false**.

Because no hypothesis survived the frozen selection gates plus global Holm correction, no internal-validation candidate existed and protected performance could not be opened. This is a valid negative scientific result, not a reason to modify thresholds, costs, horizon, candidate direction, winner rule, or multiplicity treatment.

## Accepted negative closeout

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

Target-machine closeout result: **PASS / `ACCEPTED_NEGATIVE`**.

Accepted evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Accepted artifact SHA-256 values:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists artifact: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

Historical supported modern alpha remains **0** and Phase33 remains blocked. The protected holdout is still unconsumed and remains available only to a later scientifically valid, materially different preregistered mechanism. This XBRL family may not be retuned after observing this development result.
