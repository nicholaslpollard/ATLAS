# FINRA Consolidated Short Interest — PIT Evidence-Binding Repair

Status: **TARGET FAILURE PRESERVED; NARROW MECHANICAL REPAIR IMPLEMENTED; MARKET OUTCOMES STILL UNREAD**

Parent target head that failed closed:

`18aa44e29837873878275b8e7d3f21d035b61788`

Frozen scientific fingerprint, unchanged:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Development implementation fingerprint, unchanged:

`f5b99a52bf0e9d101b53493e0012a7a60d24b301f904d4b9958dc03638432a5f`

Repair contract:

`alpha-gate-finra-short-interest-pit-evidence-binding-repair-v1-semantic-pass-evidence-no-market-outcomes`

Repair fingerprint:

`12491a2008d6d629e55d395ad3228ea069e538254a64b03d9046e9cc5ebe169a`

## Preserved failure

The first target development attempt at `18aa44e29837873878275b8e7d3f21d035b61788` stopped during Stage 1 with:

`accepted PIT audit report SHA-256 drifted`

No development market outcome was opened. Protected returns remained unread. Provider writes, broker reads/writes, orders, PAPER/LIVE submissions, automation writes, and Phase33 authority all remained zero/false.

## Root cause

The predictor mistakenly hard-coded:

`4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845`

as if it were the SHA-256 of the accepted PIT audit report. The accepted PIT target output had explicitly identified that value as the **accepted feasibility report SHA-256** embedded as the PIT audit's parent evidence. The code therefore compared the PIT report file against the hash of a different artifact.

This was an evidence-lineage implementation defect. It was not a source-feasibility failure, PIT-audit failure, hypothesis failure, or market-performance result.

## Narrow repair

The repair does not weaken or retune the scientific policy. It validates the persisted accepted PIT report semantically against the already-observed target evidence:

- PIT contract and PIT fingerprint must match the frozen audit contract;
- PIT status must remain `PIT_AUDIT_PASS`;
- accepted parent feasibility SHA must be exactly `4fb3abc3...`;
- immutable exchange-listed rows must remain 136,731;
- PIT-eligible rows must remain 63,761;
- unique PIT instruments must remain 8,054;
- all 12 source files and all 24 Massive PIT snapshots must remain recorded;
- all ten accepted PIT gates must remain true;
- accepted status counts are bound exactly;
- the exact 12 frozen audit settlement dates are required;
- every recorded source file must retain a valid SHA-256 field;
- failures must remain empty;
- alpha hypotheses must still have been unfrozen during PIT audit;
- performance must still have been unevaluated;
- target outcome rows and protected return rows must remain zero;
- protected holdout must remain unconsumed;
- provider/broker/order/PAPER/LIVE/automation authority must remain zero/false.

Those accepted semantics produce the frozen repair fingerprint `12491a20...`.

The raw PIT report SHA is still recorded diagnostically in the regenerated predictor report, but it is no longer confused with the parent feasibility report SHA.

## Scientific boundary

Nothing in this repair changes:

- the four frozen hypotheses;
- LONG/SHORT directions;
- position-change or crowding thresholds;
- the 116-date predictor reconstruction schedule;
- development/protected chronology;
- 63-session primary horizon;
- costs or stress costs;
- split censoring;
- chronological selection/internal partition and purge;
- dependence-aware bootstrap;
- global Holm-Bonferroni multiplicity control;
- robustness/concentration gates;
- winner/finalist rules;
- protected-return blindness;
- broker or trading authority.

The target runner remains two-stage and fail-closed. Development market outcomes may open only after the repaired Stage 1 source-only predictor reconstruction passes. Protected returns remain sealed regardless of the development result.
