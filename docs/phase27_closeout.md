# Phase 27 Closeout — Cross-Sectional Expected-Return Learning & Ranking

## Status

**Target research evidence:** COMPLETE / VALID NEGATIVE

**Full phase disposition:** ACCEPTED_NEGATIVE

Phase 27 tested the frozen eight-hypothesis cross-sectional expected-return/ranking policy without changing its scientific gates after performance was observed. The complete target-machine phase-end closeout passed on 2026-08-27 and bound the already-produced research artifacts without rerunning model search or reading new protected performance.

## Target-machine research evidence

The target research run executed from pre-target research head:

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

## Final target closeout evidence

The final closeout executed from exact branch head:

`bfc1c9898a6eb67bb6a9050c8d53802a887a940d`

Target command:

`python scripts/run_phase27_closeout.py`

Observed closeout result:

- Phase 27 closeout: `PASS`;
- disposition: `ACCEPTED_NEGATIVE`;
- selection survivors: `[]`;
- selection winners: `[]`;
- internal-validation finalists: `[]`;
- supported candidates: `[]`;
- protected candidate rows read: `0`;
- protected return rows read: `0`;
- protected holdout consumed: `False`;
- end-to-end anti-workaround audit: `True`;
- Phase 28 signal-to-trade entry satisfied: `False`;
- provider/broker/order/PAPER/LIVE activity: `0 / 0 / 0 / 0 / 0`;
- final pass: `True`.

The target closeout therefore accepts the negative scientific result and explicitly keeps downstream signal-to-trade construction blocked because no validated `SUPPORTED` alpha exists.

## Protected-evidence state

Because no candidate survived selection, the phase never created an internal finalist. The confirmation stage therefore used the zero-finalist path and did not open the inherited Phase 26 holdout. The final closeout independently confirmed that no protected read plan or protected outcome artifact was created and that the protected holdout remains scientifically unopened.

The holdout may only be used by a later separately preregistered alpha phase while this zero-read state remains provable. A later phase must not treat “available” as permission to read it repeatedly. The first future protected-return read permanently consumes the holdout.

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

The Phase 27 research run was therefore not rerun merely to remove warning output.

## Acceptance conclusion

Phase 27 is complete and **ACCEPTED_NEGATIVE**. The phase answered its frozen scientific question correctly, earned no new trading authority, consumed no protected returns, and preserved all safety and authority boundaries.

The next numbered phase must remain an alpha-research phase rather than signal-to-trade construction. It must test a materially different source of predictive structure rather than retuning Phase 26 rule families or Phase 27 same-session self-feature ranking models.
