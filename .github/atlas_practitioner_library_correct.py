from pathlib import Path

readme = Path('README.md')
roadmap = Path('docs/roadmap.md')
r = readme.read_text(encoding='utf-8')
m = roadmap.read_text(encoding='utf-8')

r_start = r.index('## Planned practitioner strategy library and confluence architecture\n')
r_end = r.index('## How progress is reported\n', r_start)

readme_block = r'''## Planned practitioner strategy library and confluence architecture

ATLAS already contains more practitioner work than the current four-strategy B35
pack. The accepted A33/B33 reference library has **six daily practitioner families
with nine direction-specific policies**, and B34/B35 adds **four intraday/opening
families**. Those ten existing families are retained; the successor package adds
**eight genuinely new mechanisms** for a planned **18-family practitioner library**.
Do not duplicate an existing mechanism under a new name merely because a later chat
rediscovers it.

The active B35 experiment remains frozen around its four B34 strategies and **must
not be modified while that replay is running**. The broader library is successor
work under a new preregistered fingerprint.

### Existing practitioner families to retain

1. **50/200 moving-average trend cross / Golden Cross** —
   `ma_trend_cross_50_200_long_v1`. The accepted policy uses the standard 50-session
   SMA crossing above the 200-session SMA, 201 sessions minimum history, ATR-based
   risk, and reverse-cross/maximum-hold exit logic. This is already ATLAS's Golden
   Cross implementation; do not create a duplicate `golden_cross` strategy.
2. **20/50 EMA pullback continuation** — `ema_pullback_20_50_long_v1`. Established
   EMA uptrend, bounded pullback into the 20/50 trend zone, objective recovery,
   ATR/pullback-low risk geometry and finite holding horizon.
3. **12/26/9 MACD momentum shift** — `macd_shift_12_26_9_long_v1` and
   `macd_shift_12_26_9_short_v1`. Long requires an upside signal cross below zero;
   short mirrors it above zero. The short profile remains research-only for account
   admission until borrow/locate/recall economics exist.
4. **RSI trend-filtered recovery / mean reversion** —
   `rsi_recovery_14_trend_long_v1`. RSI(14) recovery through the frozen level inside
   the accepted long-trend filter; strong-trend behavior is measured rather than
   assumed to mean-revert.
5. **20-session Donchian high-volume breakout** —
   `donchian_breakout_20_volume_long_v1` and
   `donchian_breakout_20_volume_short_v1`. Prior rolling-channel escape, aligned
   trend and relative-volume evidence, with the decision bar excluded from the prior
   boundary. Short remains research-only for account admission.
6. **20-session Bollinger squeeze breakout** —
   `bollinger_squeeze_breakout_20_long_v1` and
   `bollinger_squeeze_breakout_20_short_v1`. Prior-session compression followed by a
   directional band escape, relative-volume evidence, ATR risk and finite hold.
7. **Gap continuation** — `b34_gap_continuation_v1`. Material overnight gap followed
   by the frozen continuation trigger; prior regular close anchors the B34/B35 risk
   rule.
8. **15-minute opening-range breakout** —
   `b34_opening_range_breakout_15m_v1`. Uses the completed 09:30-09:44 ET opening
   range and only acts after the range is information-safe; the opposite boundary
   anchors risk.
9. **Premarket relative-volume consolidation breakout** —
   `b34_premarket_relvol_consolidation_v1`. Requires unusual premarket participation,
   an objective premarket consolidation and the frozen post-open breakout.
10. **Highest-volume-day style** — `b34_highest_volume_day_style_v1`. Tests the
    practitioner thesis that exceptional current premarket participation versus
    prior high-volume sessions, combined with the frozen price-structure trigger,
    can identify continuation.

### Eight new successor families

The next package adds only mechanisms that materially broaden the library. Exact
lookbacks, tolerances, bar authority, stops, targets and exits are frozen before any
new performance is opened.

11. **Bollinger-band mean reversion — `pract_bollinger_mean_reversion_v1`.** Detect a
    price excursion to/outside a frozen Bollinger envelope and require objective
    rejection/re-entry toward the band structure. A band touch alone is not a trade.
    Band width, trend regime, volume and volatility remain explicit conditional
    evidence so ATLAS can learn where mean reversion does or does not work.
12. **ATR volatility-expansion / consolidation breakout —
    `pract_atr_volatility_expansion_v1`.** Identify a normalized low-ATR/range
    contraction, then require directional price/range expansion beyond a frozen
    boundary. ATR measures volatility and supplies adaptive risk geometry; it does
    not choose direction by itself.
13. **VWAP reclaim / reject — `pract_vwap_reclaim_reject_v1`.** Intraday session-VWAP
    setup. Long research signal requires trading below VWAP followed by a
    deterministic reclaim-and-hold; the mirrored reject is the short research
    profile. Closed bars and an explicit confirmation rule are required; a single
    touch/cross is insufficient.
14. **Pivot support/resistance breakout — `pract_pivot_sr_breakout_v1`.** Build
    information-safe structural support/resistance from prior deterministic pivots
    or accepted ranges, then fire only on a confirmed boundary break. Relative
    volume, OBV and breakout distance are recorded as corroborating evidence rather
    than made hidden mandatory filters. This differs from Donchian by using
    structural pivot levels instead of a simple rolling extreme.
15. **Head-and-Shoulders / inverse Head-and-Shoulders —
    `pract_head_shoulders_v1`.** A shared deterministic pivot engine must identify
    the five alternating pivots that form left shoulder, head, right shoulder and
    the two neckline points. Freeze shoulder-similarity, head-prominence, spacing,
    neckline-slope and prior-trend rules. The setup is incomplete until an
    information-safe neckline break. Classic H&S is research-only short; inverse H&S
    is the long counterpart. Volume and formation duration are confirmation features.
16. **Double top / double bottom — `pract_double_top_bottom_v1`.** Require two
    separated tests of approximately the same resistance/support region, a material
    intervening reversal, and a break of the intervening neckline/support/resistance
    before firing. Double bottom is the long counterpart; double top is research-only
    short until short admission is available.
17. **Flag / pennant continuation — `pract_flag_pennant_v1`.** Require an objective
    impulse leg followed by a bounded, short consolidation with frozen retracement
    and contraction geometry, then a breakout in the original direction. Impulse
    strength, consolidation tightness, volume and breakout quality are retained as
    separate evidence.
18. **Triangle breakout — `pract_triangle_breakout_v1`.** Fit deterministic converging
    support/resistance boundaries from repeated prior pivots, classify ascending,
    descending or symmetrical geometry, and fire only on an information-safe
    boundary breakout. Breakout direction controls the signal; the visual pattern
    name alone never does.

Cup-and-handle, candlestick-only patterns, stochastic-only systems and other popular
setups remain backlog candidates. Add them later only if they introduce a genuinely
new mechanism or evidence source rather than another correlated restatement of an
existing family.

### Confluence / evidence-strength layer

ATLAS will **not** turn simultaneous strategy alerts into a naive confidence vote.
Every strategy fires independently and keeps its own lineage, outcome history and
standalone statistics. A separate confluence layer asks whether *independent*
corroborating evidence improves conditional probability, net expectancy, downside or
capital efficiency.

Evidence is grouped into at least seven families: **trend**, **momentum**,
**volume/participation**, **price structure**, **volatility**, **chart pattern**, and
**context** (market/sector regime, liquidity, price band, time of day and other
point-in-time state). Raw same-direction strategy count is recorded, but correlated
signals inside one family are capped/regularized so several moving-average-derived
signals cannot masquerade as several independent confirmations. Distinct-family
agreement is measured separately. Opposing/conflicting evidence is preserved as a
negative feature; it is never silently removed.

This is why ATLAS should not initially create a new hard-coded "EMA + MACD" strategy:
the existing EMA-pullback and MACD families remain independently testable, and the
confluence layer can directly measure whether their same-direction agreement adds
value beyond either signal alone.

Research compares three systems: **A) standalone strategies**, **B) explicit
confirmation-filter variants**, and **C) confluence-ranked candidates**. First report
conditional outcome tables without invented manual point weights. If sample size and
stability justify it, a later interpretable conventional probability/expectancy model
may learn weights from training-only walk-forward data. Any displayed 0-100 strength
or confidence must map to a documented calibrated probability, percentile or frozen
score; it cannot be an arbitrary sum of indicators.

Confluence inputs may include primary strategy, distinct evidence-family agreement,
opposing signals, regime, trend, momentum, volume, volatility, structure, liquidity,
estimated cost, signal age and time-of-day. Same-session/future outcomes are forbidden
inputs. Confluence itself is a hypothesis and must beat standalone baselines out of
sample before it can affect qualification or capital priority.

### Controlled calibration and refinement

A losing v1 is evidence, not an instruction either to discard the mechanism
immediately or to tune it until green. After each frozen v1 evaluation, perform one
structured diagnostic review covering regime, liquidity, price band, time, volatility,
setup intensity, entry delay, MFE/MAE, stop/target path, cost drag, unresolved/no-entry
rate, loss concentration, losing streaks and confluence/conflict state.

Per strategy family and research cycle, create **no more than three materially
distinct v2 candidates by default**. Each requires a ledgered failure/opportunity
rationale, practitioner/statistical basis, exact rule change, declared trial count and
untouched evaluation source before performance is opened. Dense threshold sweeps,
tiny parameter stepping and repeated same-sample optimization are prohibited.
Original v1 results remain permanently ledgered. Data used to propose v2 is
training/diagnostic evidence only; v2 promotion requires a fresh walk-forward or other
untouched evaluation under a new fingerprint. Consumed master evidence is never
recycled, and an existing blind window is never reassigned after results are known.

### Implementation order and efficiency

B35 finishes first under its existing four-strategy fingerprint. After B35 closeout,
run the frozen B35 strategy x condition evidence and preregistered selector exactly as
planned. Then freeze the **eight-new-family successor contract** plus the confluence
feature schema before opening their outcomes. Reuse the six accepted daily families
and four B34 intraday families rather than reimplementing them. Shared point-in-time
feature extraction, canonical bars, indicator primitives, deterministic pivots and
the validated parallel execution pattern should be reused where exact-equivalent,
while every strategy evaluator remains independently testable and deterministic.

The destination is not one universal strategy. It is a library of versioned
mechanisms whose standalone evidence, condition profile, confluence value, costs and
correlation are known well enough for ATLAS to rank good opportunities, abstain when
evidence is weak, and explain why one candidate outranks another.

'''
r = r[:r_start] + readme_block + r[r_end:]

m_start = m.index('## 19A. Practitioner strategy-library expansion, confluence, and calibration\n')
m_end = m.index('## 20. Phase/package cadence and progress reporting\n', m_start)

roadmap_block = r'''## 19A. Practitioner strategy-library expansion, confluence, and calibration

**Status: PLANNED SUCCESSOR WORK; DO NOT ALTER THE ACTIVE B35 FOUR-STRATEGY
EXPERIMENT.** ATLAS already has **six accepted daily practitioner families** in the
A33/B33 reference catalog plus **four frozen B34 intraday/opening families**. The next
library package therefore targets **18 total families by adding eight new mechanisms**,
not by cloning the existing Golden Cross, EMA, MACD, RSI, Donchian or Bollinger-squeeze
work under new ids.

### 19A.1 Retained ten-family base

A33/B33 retained families and exact existing policy ids:

- Golden Cross / 50-200 SMA trend transition — `ma_trend_cross_50_200_long_v1`.
- 20/50 EMA pullback continuation — `ema_pullback_20_50_long_v1`.
- 12/26/9 MACD momentum shift — `macd_shift_12_26_9_long_v1` and
  `macd_shift_12_26_9_short_v1`.
- RSI(14) trend-filtered recovery — `rsi_recovery_14_trend_long_v1`.
- 20-session Donchian high-volume breakout —
  `donchian_breakout_20_volume_long_v1` and
  `donchian_breakout_20_volume_short_v1`.
- 20-session Bollinger squeeze breakout —
  `bollinger_squeeze_breakout_20_long_v1` and
  `bollinger_squeeze_breakout_20_short_v1`.

B34/B35 retained families:

- `b34_gap_continuation_v1`;
- `b34_opening_range_breakout_15m_v1`;
- `b34_premarket_relvol_consolidation_v1`;
- `b34_highest_volume_day_style_v1`.

These accepted/frozen versions remain immutable historical hypotheses. Successor
research may create explicitly versioned v2 candidates after diagnostic review, but
must never silently rewrite v1.

### 19A.2 Eight genuinely new families

Freeze under a new successor fingerprint before opening any new performance:

- `pract_bollinger_mean_reversion_v1` — Bollinger excursion plus deterministic
  rejection/re-entry; band touch alone does not fire.
- `pract_atr_volatility_expansion_v1` — normalized low-ATR/range consolidation
  followed by directional range/price expansion; ATR supplies volatility/risk, not
  direction.
- `pract_vwap_reclaim_reject_v1` — closed-bar intraday VWAP reclaim-and-hold long
  profile and mirrored reject short research profile.
- `pract_pivot_sr_breakout_v1` — confirmed breakout of deterministic structural
  pivot support/resistance; volume/OBV participation retained as separate evidence.
- `pract_head_shoulders_v1` — objective five-pivot H&S/inverse H&S with frozen
  shoulder similarity, head prominence, spacing, prior-trend and neckline rules;
  neckline break required.
- `pract_double_top_bottom_v1` — two separated level tests, material intervening
  reversal and neckline/support/resistance break required.
- `pract_flag_pennant_v1` — objective impulse leg, bounded continuation consolidation
  with frozen retracement/contraction geometry, then same-direction breakout.
- `pract_triangle_breakout_v1` — deterministic repeated-pivot converging boundaries,
  ascending/descending/symmetrical classification and information-safe breakout.

For every new family freeze before performance: exact timeframe/bar authority;
indicator definition; lookback/minimum history; pivot algorithm; normalized geometry
and tolerances; entry clock; duplicate-signal rule; stop/target/time exit; costs;
long/short authority; sample/coverage minimums; condition dimensions; robustness
perturbations; and trial/fingerprint identity. Chart patterns use one deterministic
shared pivot/geometry engine. Manual visual labeling is forbidden.

### 19A.3 Confluence is evidence, not vote counting

A strategy's fired/not-fired state remains immutable and independently testable.
Confluence consumes those signals plus point-in-time context without rewriting the
underlying strategy. Preserve primary strategy/direction, raw same-direction signal
count, distinct evidence-family count, exact contributors, opposing evidence,
estimated costs, signal age and relevant PIT context.

Evidence families are at least **trend**, **momentum**, **volume/participation**,
**price structure**, **volatility**, **chart pattern**, and **context/regime**.
Correlated indicators within one family are capped/regularized or otherwise prevented
from multiplying confidence. Five trend indicators are not equivalent to independent
agreement across trend, volume, structure, volatility and regime.

Do not initially create redundant composite strategies such as a separate EMA+MACD
rule solely because both already exist. Keep EMA pullback and MACD shift standalone,
then measure whether same-direction agreement adds value in the confluence layer.

Evaluate three preregistered systems: **standalone**, **hard-confirmation variant**,
and **confluence ranking**. Start with transparent stratified outcome tables, not
hand-designed point scores. If evidence supports it, a later conventional model may
estimate calibrated probability and/or net expectancy from training-only walk-forward
features with leakage guards, regularization and explicit baselines. The operator UI
may show a 0-100 strength only when it maps to a documented calibrated probability,
percentile or frozen score.

Confluence earns authority only if untouched evidence shows improvement over
standalone strategies in probability/expectancy, downside and/or capital efficiency.
If extra confirmation only reduces sample size or arrives too late, retain the simpler
strategy.

### 19A.4 Post-result diagnosis and bounded refinement

Every v1 receives a structured post-result review whether positive or negative.
Slice by regime, liquidity, price band, time, volatility, setup intensity, entry
delay, MFE/MAE, stop/target behavior, cost drag, unresolved/no-entry rate,
concentration, losing streak and confluence/conflict state. This is failure/opportunity
attribution, not retrospective threshold shopping.

Default calibration budget: **no more than three materially distinct v2 candidates
per family per research cycle**. Each successor must state the observed failure mode,
practitioner/statistical rationale, exact rule change, total trial count and untouched
evaluation source before performance is opened. Dense grids and tiny threshold
stepping are prohibited. Preserve v1. Data that motivated v2 may diagnose/train but
cannot independently validate v2; promotion requires fresh walk-forward or other
untouched evidence under a new trial/fingerprint. Consumed master evidence is never
reused and blind windows are never reassigned after results are known.

### 19A.5 Efficient shared implementation

Use one point-in-time primitive/context layer for OHLCV, SMA/EMA, RSI, MACD,
Bollinger statistics, ATR/ATRP, VWAP, relative volume/OBV, rolling highs/lows,
deterministic pivots, regime/liquidity and session context. Feed immutable views to
independent strategy evaluators. Reuse process-local infrastructure and parallelize
independent work under the validated ATLAS efficiency protocol. Avoid redundant full
feature lakes and repeated expensive scans when exact-equivalent shared computation
is possible. Golden-output/receipt equivalence remains mandatory whenever execution
mechanics change.

### 19A.6 Ordered successor work after B35

1. Close and validate the active B35 canonical replay; record final throughput and
   scientific summary without changing the frozen four-strategy result.
2. Produce the preregistered B35 strategy x condition evidence and selector result.
3. Freeze the exact **eight-new-family** successor contract and confluence feature
   schema; bind the six daily plus four B34 families as retained baseline lineage.
4. Implement shared PIT indicators/pivots and the eight independent new evaluators;
   run source-only, semantic and exact-equivalence tests.
5. Run expanded DEVELOPMENT evidence with standalone strategies first.
6. Evaluate hard confirmation and confluence as separate hypotheses, including
   redundancy, conflict, costs and sample-size effects.
7. Perform one bounded diagnostic/calibration cycle; preregister up to three justified
   v2 candidates per family and evaluate them only on untouched evidence.
8. Promote nothing automatically. Survivors become candidates for the next
   prospective/PAPER evidence gate; failures stay in the ledger and guide the next
   research family.

This Track-B expansion does not block Track A product completion. PAPER plumbing may
advance independently under its own authority while strategy research continues.

'''
m = m[:m_start] + roadmap_block + m[m_end:]

m = m.replace(
    'then freeze and implement the 18-strategy successor practitioner pack plus the separate confluence/strength layer defined in Section 19A.',
    'then freeze and implement the eight-new-family successor package that expands the retained ten-family base to 18 total families, plus the separate confluence/strength layer defined in Section 19A.',
)

readme.write_text(r, encoding='utf-8')
roadmap.write_text(m, encoding='utf-8')
