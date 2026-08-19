# Deferred Market-Regime History Backfill

Status: **DEFERRED / NON-BLOCKING**

Phase 10 Gate 5 remains accepted. Gate 6 proceeds with the locked core-33 predictor matrix.

## What the 77.96% coverage means

The accepted Phase 9 market-regime history currently covers 5,136,676 of 6,588,579 Gate 2 candidate rows (77.96%), from 2023-06-01 through 2026-08-14.

The missing 22.04% is primarily a historical warm-up / source-access boundary, not an accuracy or trust score for the regime classifier. The accepted Phase 9 regime policy requires:

- fully warmed daily quantitative inputs, including long-horizon features such as EMA200; and
- 252 strictly prior fully warmed sessions before expanding point-in-time threshold bands are valid.

The ML observation history begins 2021-08-16, so the regime engine cannot legitimately classify the earliest ML observations without older seed history.

## Provider-access evidence

Target-machine probe:

`python scripts/probe_massive_history_access.py --dataset 1d --start 2019-01-01 --end 2021-08-15`

Observed result:

- remote daily sessions listed: 660
- readable sessions under the current Massive S3 subscription: 0

This confirms that the current limitation is provider-subscription history access, not missing files caused by an ATLAS defect.

## Current production decision

Until deeper daily history is available:

- exactly 33 Phase 6 quantitative features remain the production ML predictor matrix;
- market regime remains point-in-time-safe evaluation / segmentation metadata where available;
- sector and ticker regime predictors remain excluded until their historical attachment is independently proven date-safe;
- no synthetic `UNKNOWN` market-regime predictor is introduced for early history, because it would closely proxy calendar era;
- Gate 6 and the rest of Phase 10 are not blocked by the market-regime coverage gap.

## Future backfill path

When deeper daily history becomes economically practical, prefer reproducing the exact accepted Phase 9 market-regime methodology rather than silently substituting a proxy regime.

Recommended procedure:

1. acquire enough pre-2021 daily stock aggregate history to warm the required technical inputs and at least 252 prior threshold-memory sessions;
2. materialize only the daily features required by the accepted regime policy;
3. replay the market regime point-in-time from the extended seed history;
4. compare the newly replayed regime with the already accepted 2023-06-01 onward Phase 9 history over the overlap window;
5. require high agreement and no material increase in opposite-direction lag before accepting the extended history;
6. version any changed regime semantics with a new contract rather than silently rewriting Phase 9 history;
7. only then benchmark `core33` versus `core33 + market regime` on identical chronological OOS windows before promoting regime to a production predictor.

A future deeper-history backfill is therefore an enhancement path, not technical debt that invalidates the current ML foundation.
