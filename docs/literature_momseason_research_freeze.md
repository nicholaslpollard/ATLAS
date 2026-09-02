# LIT-01 Research Gate and Prospective Scientific Freeze

Status: **EXPERIMENTAL / NON-AUTHORITATIVE / PRE-OUTCOME**

This document freezes the development-stage scientific contract for LIT-01, the Heston-Sadka calendar-month return-seasonality family, after source semantics and the literature-native population have been established but **before any ATLAS development or protected target return is opened**.

It does not change mainline alpha status, Phase33 authority, PAPER, LIVE, broker behavior, or production strategy routing.

## Preconditions accepted before this freeze

The native source run at branch head `af59bd7ea22061032a5d0d551824f8d291946f6a` returned:

- `NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW`
- native endpoint rows: 192,063
- `AVAILABLE`: 191,990
- `ZERO_BAR`: 73
- reused previously accepted adjusted endpoints: 190,846
- supplemental endpoints: 1,217
- supplemental provider calls: 86
- provider rejections: 0
- target outcome rows read: 0
- protected return rows read: 0
- protected holdout consumed: false
- broker/order/PAPER/LIVE activity: 0

Native predictor coverage was:

| Hypothesis | Native formation rows | Identity-defined | Adjusted-defined | Adjusted / identity | Monthly adjusted cross-section |
|---|---:|---:|---:|---:|---:|
| `momseason_short_year1` | 124,082 | 114,718 | 114,675 | 99.9625% | min 1,760 / median 1,894 / max 2,048 |
| `momseason_years2_5` | 124,082 | 105,553 | 105,511 | 99.9602% | min 1,645 / median 1,772.5 / max 1,864 |

The remaining loss is principally historical identity/reference availability, not adjusted-price-provider failure. The population-coverage contract is valid, full native source scope is proven, and no unexplained severe source-to-signal bottleneck remains.

## Fixed external family

Exactly two hypotheses are in the family. Neither may be removed after seeing ATLAS returns.

1. `momseason_short_year1` / OpenSourceAP `MomSeasonShort`
   - positive expected direction
   - predictor: total return in the same calendar month one year earlier
2. `momseason_years2_5` / OpenSourceAP `MomSeason`
   - positive expected direction
   - predictor: simple average of all **available valid** same-calendar-month total returns among years 2, 3, 4, and 5
   - at least one valid lag is required

OpenSourceAP commit bound by the freeze: `8db892442c2c3a3779b0f1eac4370d3655be15a1`.

Adaptive deletion of a hypothesis and adaptive selection of a preferred 1/2/3/4-lag subgroup are prohibited.

## Native population

The primary replication does not inherit the ATLAS discovery route.

Formation universe:

- PIT Massive reference snapshot
- `security_type == CS`
- `primary_exchange in {XNYS, XASE}`
- safe stable ATLAS identity required

Historical signal observations may be on XNYS, XASE, or XNAS, matching the broader OpenSourceAP common-stock master-table scope before the MomSeason formation filter. A ticker change within a historical lag month is permitted only when the same stable ATLAS `instrument_id` proves continuity.

## Portfolio construction

For every complete development target month:

1. calculate the frozen predictor from information fully available before the target month;
2. rank the native formation cross-section by predictor value;
3. equally weight the top decile as the long leg;
4. equally weight the bottom decile as the short leg;
5. hold for one target calendar month;
6. gross portfolio return = EW top-decile target-month total return minus EW bottom-decile target-month total return.

The target-month security total return is defined as adjusted month-end close divided by prior month-end adjusted close minus one. Alpaca `1Day`, `adjustment=all`, historical endpoint `asof` semantics are the price source; stable ATLAS instrument identity remains the identity authority.

The primary test is the **native literature signal**. Phase25 WARM/HOT routing and other ATLAS context filters are not applied to the primary replication. ATLAS-layer attribution can be studied only after the native result is known.

## Independent sample and development window

The independent inferential unit is one target-calendar-month long-short portfolio return, **not an individual stock row**.

Frozen development months:

- first: 2021-09
- last: 2026-04
- count: **56 complete calendar months**

May 2026 is the purge/boundary month and is not development evidence.

The large underlying stock cross-section improves portfolio construction and source coverage but does not turn 56 monthly return realizations into hundreds of thousands of independent observations.

## Transaction costs

The freeze retains the accepted ATLAS Phase26 convention:

- primary: **10 bps per one-way leg turnover**
- stress: **25 bps per one-way leg turnover**

Actual research must compute realized one-way turnover separately for long and short legs and sum the two cost drags. It must not blindly subtract a fixed full-turnover amount if realized turnover is lower.

For conservative positive-path power calibration only, full turnover of both legs is assumed:

- primary spread drag: 20 bps
- stress spread drag: 50 bps

## Primary statistical gate

The two hypotheses are one fixed family.

- family alpha: 0.05
- multiplicity: Holm-Bonferroni across exactly two hypotheses
- empirical bootstrap replicates: 2,000
- bootstrap: circular block bootstrap
- block length: **12 calendar months**, preserving one complete seasonal cycle
- one-sided expected direction: positive
- lower confidence bound: 90% one-sided

A hypothesis passes the primary development gate only if all are true:

1. primary after-cost mean > 0;
2. 90% one-sided block-bootstrap lower confidence bound > 0;
3. one-sided block-bootstrap p-value is rejected after Holm correction across both hypotheses;
4. 25-bps-per-leg turnover-stress mean > 0.

The family produces an internal finalist if at least one of the two fixed hypotheses passes all primary checks. Both hypotheses remain reported regardless of outcome; there is no runner-up substitution or post-result family shrinking.

## Robustness reporting

The following are frozen as robustness/descriptive outputs and may not be used to create a new adaptive hypothesis after viewing returns:

- four chronological development folds;
- twelve calendar-month-of-year slices;
- `momseason_years2_5` valid-lag-count slices 1/2/3/4;
- gross literature-replication result alongside the after-cost ATLAS result.

## Positive-path calibration

The generic ATLAS prospective-freeze framework requires proof that the gate is arithmetically reachable and can detect a plausible positive effect before real outcomes are opened.

Calibration therefore uses **synthetic monthly portfolio returns only**:

- 256 deterministic trials;
- 56 synthetic months per trial;
- external gross monthly effect anchors from OpenSourceAP SignalDoc:
  - `momseason_short_year1`: 1.15%
  - `momseason_years2_5`: 0.67%
- common prospective monthly spread-volatility stress: 3.5%;
- full-turnover primary/stress costs: 20/50 bps;
- exact same 12-month block bootstrap and Holm family correction used by the future development gate.

The preregistered minimum family detection rate is two-thirds. This is intentionally a **family-level** calibration because the experiment contains two externally fixed hypotheses and either may reproduce. The fixed 56-month modern development window has materially less power than the original multi-decade literature sample; a negative development result must therefore be interpreted as an accepted modern non-replication under this frozen design, not as mathematical proof that the historical mechanism never existed.

No ATLAS development return is used to select the synthetic volatility, effect anchors, seeds, bootstrap configuration, or target detection rate.

## Missing outcomes, delistings, and survivorship

The target cohort is fixed at formation. Future terminal-price availability is not an eligibility filter.

Prohibited:

- silently dropping a holding because it delists during the target month;
- silently dropping a missing terminal adjusted bar;
- imputing zero return;
- using an ungrounded last-price return;
- choosing a corporate-action/delisting treatment after observing the sign of the missing outcome.

If a complete source-grounded total return cannot be reconstructed for a formation holding, the affected primary portfolio month is source-incomplete and cannot count as confirmatory evidence until a prospectively allowed provider-grounded resolution is established. This fail-closed rule prevents survivorship bias before outcomes are opened.

## Protected policy

The existing master protected window remains unconsumed.

- current protected interval: 2026-05-12 through 2026-08-11
- complete LIT-01 target months currently available inside it: **2**
- frozen minimum: **12 complete target calendar months**
- current protected window sufficient: **false**

If the development gate produces an internal finalist, ATLAS must reserve a **new prospective protected window containing at least 12 complete calendar months** before reading any of those protected returns. The 12-month requirement may not be weakened after development results are known.

## Authority boundary

A development pass on this experimental branch would mean only that a literature-defined characteristic became an **internal experimental finalist**.

It would not:

- reclassify prior ATLAS accepted-negative phases;
- establish mainline supported alpha;
- unblock Phase33 automatically;
- authorize PAPER or LIVE;
- authorize broker writes;
- merge experimental code to main;
- adopt the signal into production routing.

Any later adoption is a separate explicit operator/governance decision after the complete experimental evidence path is finished.
