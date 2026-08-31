# FINRA Consolidated Short Interest — Source-Only Negative Closeout Probe

Status: **SOURCE-ONLY NEGATIVE OBSERVED; MARKET OUTCOMES UNREAD; CLOSEOUT EVIDENCE PROBE IMPLEMENTED**

Accepted target-machine source reconstruction head:

`d312ec95752ab49a6fcbec18973faacb96d4aa89`

Frozen scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Probe contract:

`alpha-gate-finra-short-interest-source-only-closeout-probe-v1-persisted-predictor-negative-no-provider-no-market-outcomes`

## Observed source-only result

The complete frozen 116-settlement reconstruction ran successfully across all 116 official FINRA files and 232 Massive point-in-time reference snapshots. It produced 19,343 source-only predictor rows: 14,841 DEVELOPMENT and 4,502 PROTECTED.

Frozen candidate totals were:

- `rapid_short_build_crowded_short`: 2,036
- `rapid_short_build_non_crowded_short`: 8,025
- `rapid_short_cover_crowded_long`: 1,257
- `rapid_short_cover_non_crowded_long`: 8,025

All development source-count gates passed for all four hypotheses. All protected source-count gates also passed except one: `rapid_short_cover_crowded_long` did not meet the frozen protected minimum of 300 event rows. It did meet the frozen protected signal-session and unique-instrument minimums.

The source-only predictor therefore correctly returned `SOURCE_ONLY_PREDICTOR_FAIL` and stopped. Target/development outcome rows read remained 0. Protected return rows read remained 0. The protected holdout remains unconsumed.

## Scientific disposition

The frozen contract required every one of the four preregistered hypotheses to independently satisfy the development and protected source-count requirements before any development market outcome could open. Multiplicity was frozen globally across exactly four hypotheses using `HOLM_BONFERRONI_GLOBAL_4`.

Therefore the underpowered hypothesis may **not** be removed after observing the source-only result, and the 300-row minimum, 10% change-tail threshold, 80% crowding threshold, chronology, deterministic sampling cap, or global multiplicity family may not be changed to rescue this version.

The correct disposition for the exact v1 formulation is:

`ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`

This is a source-feasibility negative, not a performance negative. No market-return claim is made because development returns were never opened.

## Evidence probe

The closeout probe reads only the already-persisted predictor report and predictor JSONL rows. It performs no FINRA request, Massive request, price read, benchmark read, protected-return read, broker access, or order/execution action.

It independently binds:

- exact predictor/stage/candidate counts;
- exact source-only gate matrix and diagnostics;
- 116 FINRA source files and 232 Massive reference snapshots from the accepted run;
- accepted PIT report SHA-256 and semantic evidence-binding fingerprint;
- actual predictor-report and predictor-row SHA-256 values;
- exact DEVELOPMENT/PROTECTED row counts per candidate from the persisted JSONL;
- the underpowered protected candidate's exact event-row, signal-session, and unique-instrument counts;
- zero target outcome reads, zero protected-return reads, unconsumed protected holdout, and zero trading authority.

The probe is the final target-machine evidence extraction needed before repository closeout can pin the exact artifact hashes and evidence fingerprint.

## Anti-retuning boundary

This exact FINRA v1 formulation is permanently retained as a negative source-feasibility result. A future short-interest study, if ever revisited, must be explicitly preregistered as a new scientific family/version before outcomes and may not describe a post-result threshold/pruning change as the same v1 experiment.

Phase33 Signal-to-Trade remains blocked because no historically validated alpha has `SUPPORTED` authority.
