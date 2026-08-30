# Pre-Phase33 SEC XBRL Fundamental Alpha — Accepted Negative Closeout

**Final disposition: `ACCEPTED_NEGATIVE`. Protected returns were never opened. Historical supported alpha remains 0 and Phase33 remains blocked.**

## Frozen lineage

Scientific contract: `alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Development implementation fingerprint:

`3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

Accepted development target head:

`58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

## Source/identity lineage

The source-only feasibility census passed with 200 successful Company Facts documents, 170 accrual-history-ready issuers, and 92 profitability-history-ready issuers.

The initial PIT identity audit result was preserved as `AUDIT_FAIL`: 139 unambiguous mappings and 28 issuers with at least three mappings. Root-cause diagnosis showed the Massive historical query expanded the tradable identity universe by using `active=false` and non-common-stock security types.

The targeted owning-layer repair changed only the identity query semantics to exact historical CIK/date plus `active=true` and `type=CS`, retained the same 40 issuers/accessions/SEC chronology/numeric gates, and replayed local source-only caches with zero provider calls. The corrected v2 result was `AUDIT_PASS`: 171 unambiguous common-stock mappings and 38 issuers with at least three mappings. The original v1 failure remains preserved evidence.

## Frozen experiment

Exactly six hypotheses were preregistered before market outcomes:

- gross-profitability improvement LONG;
- gross-profitability deterioration SHORT;
- cash-profitability improvement LONG;
- cash-profitability deterioration SHORT;
- accrual-quality improvement LONG;
- accrual-quality deterioration SHORT.

The primary horizon was 63 XNYS sessions. Development was chronologically partitioned into selection and internal validation with a 63-session purge. Selection used frozen direction-specific costs, hard sample/robustness/concentration gates, dependence-aware bootstrap evidence, and global Holm–Bonferroni across all six hypotheses. At most one winner per direction could proceed, chosen only from selection evidence. Internal validation could confirm or reject but could not choose a candidate. Runner-up substitution was forbidden. Protected performance was finalist-only.

## Accepted target development result

Target result: `ACCEPTED_NEGATIVE_DEVELOPMENT`.

- predictor rows: **5,536**;
- development predictor rows: **4,157**;
- protected predictor rows: **1,379**;
- usable development outcomes: **3,963**;
- exact stock paths missing/censored: **123**;
- split-crossing paths censored: **71**;
- selection passers after every hard gate plus Holm: **0**;
- selection winners: **0**;
- internal finalists: **0**;
- protected-return eligible finalists: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- Phase33 authority: **false**.

Because the frozen development screen produced no selection passer, no candidate was eligible for internal validation or protected performance. No protected source precheck or protected return read could change the disposition.

## Accepted closeout evidence

Target closeout runner result: **PASS**.

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Accepted artifact SHA-256 values:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists artifact: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

The closeout runner reads only persisted target artifacts. It performs zero provider calls, zero new market-outcome reads, zero broker reads/writes, zero orders, zero PAPER/LIVE submissions, and zero automation writes.

## Scientific interpretation

This is a valid negative test of a materially different information mechanism. It does not prove that accounting fundamentals never contain predictive information; it proves that this exact preregistered six-hypothesis PIT quarterly change family did not earn ATLAS support under its frozen chronology, costs, statistical controls, and robustness requirements.

The family is closed. It may not be rescued by changing thresholds, horizon, costs, direction, feature definitions, winner rules, multiplicity treatment, issuer sample, or by opening the protected holdout after observing the negative development result.

Historical supported modern alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. The master protected outcome window `2026-05-12..2026-08-11` remains unconsumed and may be used only by a later scientifically valid, materially different preregistered mechanism.
