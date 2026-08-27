# Phase 27 Closeout — Cross-Sectional Expected-Return Learning & Ranking

## Status

**Target research evidence:** COMPLETE / VALID NEGATIVE

**Full phase disposition:** PENDING TARGET CLOSEOUT BINDING

Phase 27 tested the frozen eight-hypothesis cross-sectional expected-return/ranking policy without changing its scientific gates after performance was observed.

## Target-machine research evidence

The target run executed from pre-target research head:

`55f8ca32ffd87904a22b206ef8d73120b4edf229`

Frozen policy fingerprint:

`63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`

Observed target result:

- development model rows: `18,111`;
- protected predictor rows: `920`;
- selection survivors: `[]`;
- selection winners: `[]`;
- internal-validation finalists: `[]`;
- protected-confirmed supported candidates: `[]`;
- protected candidate rows queried: `0`;
- protected return rows read: `0`;
- protected holdout consumed: `False`;
- independent validation: `PASS`;
- provider/broker/order/PAPER/LIVE activity: `0 / 0 / 0 / 0 / 0`;
- cumulative result: `PASS`.

This is valid negative evidence: Phase 27 ran correctly, but no frozen architecture earned historical analytical support.

## Protected-evidence state

Because no candidate survived selection, the phase never created an internal finalist. The confirmation stage therefore used the zero-finalist path and did not open the inherited Phase 26 holdout. The holdout remains scientifically unopened and may only be used by a later separately preregistered alpha phase while this state remains provable.

A later phase must not treat “available” as permission to read it repeatedly. The first future protected-return read permanently consumes the holdout.

## Post-result maintenance correction

The target run emitted repeated scikit-learn `FutureWarning` messages because the pairwise logistic implementation explicitly supplied the deprecated `penalty="l2"` argument. This warning did not change model fitting or the Phase 27 scientific result.

The implementation was repaired after the target result by expressing the same L2 regularization semantics through the supported API (`l1_ratio=0.0`). Regression coverage now promotes any future `FutureWarning` from that fit path to a test failure.

This maintenance correction does not modify:

- candidate IDs or architecture families;
- hyperparameter grids;
- predictor fields;
- score-to-signal policy;
- 20% tail;
- outcome horizon;
- costs;
- chronology/purge;
- bootstrap settings;
- Holm correction;
- evidence minimums;
- selection/internal/protected gates;
- target research artifacts or observed result.

The Phase 27 research run is therefore not rerun merely to remove warning output.

## Required final gate

The full phase-end closeout must bind the already-produced target artifacts and prove:

1. all Phase 27 artifact contracts and policy fingerprints match;
2. cumulative SHA relationships bind population, research, blindness, confirmation, and independent validation;
3. selection/winner/finalist/support relationships are consistent;
4. the zero-finalist path preserved the protected holdout with no read plan or protected outcome artifact;
5. historical support remains analytical-only with no PAPER or LIVE authority;
6. provider/broker/order/PAPER/LIVE activity remains zero;
7. the end-to-end anti-workaround audit passes;
8. no validated supported alpha exists, so downstream trade construction remains blocked.

If that gate passes, the formal Phase 27 disposition is `ACCEPTED_NEGATIVE`.
