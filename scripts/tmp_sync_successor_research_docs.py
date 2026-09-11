from pathlib import Path

README = Path('README.md')
ROADMAP = Path('docs/roadmap.md')
REGISTER = Path('docs/strategy_evidence_register.md')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'missing anchor: {label}')
    return text.replace(old, new, 1)


def append_once(text: str, marker: str, block: str) -> str:
    if marker in text:
        return text
    return text.rstrip() + '\n\n' + block.strip() + '\n'


readme = README.read_text(encoding='utf-8')
readme = replace_once(
    readme,
    '**B35 exact targeted minute perturbations are IMPLEMENTED / ACCEPTANCE ACTIVE in PR #79.**',
    '**B35 exact targeted minute perturbations are MERGED / WORKSTATION RUN PENDING.**',
    'README B35 targeted state',
)
readme = replace_once(
    readme,
    'One DEVELOPMENT-only pass freezes 27 one-axis-at-a-time strategy/variant profiles covering entry delay 0/1/2, gap threshold x0.9/1.0/1.1, ORB 14/15/16 minutes, premarket rel-vol threshold x0.9/1.0/1.1, and premarket consolidation-range x0.9/1.0/1.1 for premarket-relvol/HVD. Every group must reproduce canonical v1 fired/comparable/noncomparable counts for all baseline variants before perturbed evidence can publish. Outputs are diagnostic, hash-receipted and restartable; canonical B35 v1 is immutable, selector refit is forbidden, and no promotion/PAPER/LIVE/master/future/provider/broker authority is granted.',
    'PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`. One DEVELOPMENT-only pass freezes 27 one-axis-at-a-time strategy/variant profiles covering entry delay 0/1/2, gap threshold x0.9/1.0/1.1, ORB 14/15/16 minutes, premarket rel-vol threshold x0.9/1.0/1.1, and premarket consolidation-range x0.9/1.0/1.1 for premarket-relvol/HVD. Baseline variants are now populated from the exact accepted canonical B35 outcome files with SHA-256 verification, and tests require exact outcome-economic parity in addition to count parity. Outputs are diagnostic, hash-receipted and restartable; canonical B35 v1 is immutable, selector refit is forbidden, and no promotion/PAPER/LIVE/master/future/provider/broker authority is granted. Immediate Track-B action is the workstation run `scripts/run_b35_targeted_perturbations.py --authorize-targeted-perturbations`; do not start the successor full-library replay until this bounded diagnostic closes.',
    'README B35 targeted details',
)
readme = append_once(readme, '## Successor Strategy Lab direction — 19 families', '''
## Successor Strategy Lab direction — 19 families

After the accepted B35 targeted perturbation diagnostic closes, Track B proceeds to a new preregistered successor research package rather than modifying B35 v1. The next broad historical experiment targets **19 economic strategy families** plus a bounded set of explicitly versioned challengers. The ten retained families remain immutable baselines; nine distinct additions are planned: Bollinger mean reversion, ATR/range expansion, ADX/DMI continuation/filter, support/resistance rejection, relative-strength momentum versus market/sector, deterministic head-and-shoulders/inverse, double-top/bottom, flag/pennant/triangle continuation, and objective session-level failed-break/reclaim. Nearby parameterizations remain members of one economic family for multiplicity and confluence.

The Opening Range family receives two high-priority successor policies, not two new independent families: a **Stocks-in-Play 5-minute ORB/opening-momentum** policy using abnormal same-time opening participation and executable liquidity/volatility controls, and a **15-minute ORB close + bounded retest confirmation** challenger designed to test false-break reduction. The failed-break/reclaim family uses only observable PIT levels (initially previous-day high/low and premarket high/low) and makes no hidden-liquidity or ICT/SMC claim.

The successor experiment also adds a shared PIT context layer before confluence/ranking: broad-market alignment, ticker relative strength/weakness versus SPY, bounded higher-timeframe trend, trend maturity/extension, participation/relative volume, overnight gap, signal time, price band, realized volatility, and liquidity/execution quality. Sector-relative strength waits for an accepted PIT sector map. Context is measured first for incremental value and is not automatically a hard filter. Confluence remains separate from standalone strategy firing and counts independent evidence families rather than correlated indicators. Portfolio loss limits, simultaneous-position competition, concentration, and capital allocation remain account/PAPER-layer questions; fixed arbitrary stops/targets, human psychology rules, small discretionary watchlists, and reopened failed SEC hypotheses are not part of this successor strategy package.

The large successor run must report standalone v1 baselines, each frozen challenger, condition coverage, win rate, payoff ratio, net expectancy/net-R, cost decay, MFE/MAE, drawdown, concentration, fold stability, and abstention. The objective is broader **economically viable condition coverage**, not maximizing win rate or forcing every strategy to trade broadly. Candidate context interactions are frozen before performance, tested incrementally with multiplicity control, and any favorable condition-gated successor requires new untouched/prospective evidence before authority promotion.
''')
README.write_text(readme, encoding='utf-8')

roadmap = ROADMAP.read_text(encoding='utf-8')
roadmap = replace_once(
    roadmap,
    'Those ten existing families are retained; the successor package adds\n**eight genuinely new mechanisms** for a planned **18-family practitioner library**.',
    'Those ten existing families are retained; the successor package adds\n**nine genuinely new mechanisms** for a planned **19-family practitioner library**.',
    'roadmap family count',
)
roadmap = append_once(roadmap, '### B36 — Successor 19-family Strategy Laboratory', '''
### B36 — Successor 19-family Strategy Laboratory

B36 begins only after the merged PR #79 B35 targeted minute-perturbation workstation run closes and its exact evidence is recorded. B36 does not rewrite B35 v1 or reuse the consumed master holdout to qualify a revision.

**Core roster:** retain the ten accepted economic families as immutable baselines and add nine materially distinct mechanisms: Bollinger mean reversion; ATR/range expansion; ADX/DMI continuation/filter; support/resistance rejection; relative-strength momentum versus market/sector where data authority exists; objective head-and-shoulders/inverse; double-top/bottom; flag/pennant/triangle continuation; and objective session-level failed-break/reclaim. Cup-and-handle remains lower priority. Similar indicators/parameterizations remain one family for trials/multiplicity accounting.

**High-priority Opening Range challengers:**

- `orb_stocks_in_play_5m_v1` — literature-anchored research policy testing whether abnormal same-time opening participation plus a 5-minute opening-range break produces a viable opening-momentum specialist under realistic costs. PIT feasibility must use only information known at the decision time; threshold choices are finite and frozen before performance.
- a new versioned 15-minute ORB close/retest challenger — same economic family as ORB, designed to isolate whether close-outside-range plus bounded retest/hold confirmation reduces false breaks and MAE enough to improve net expectancy after later entry and lower trade count.

**Objective failed-break/reclaim family:** begin with previous-day high/low and premarket high/low. Define normalized breach depth, maximum reclaim time, objective reclaim/confirmation, entry, sweep-extreme stop/invalidation and one coherent exit hierarchy before performance. Do not claim hidden institutional liquidity; the test is observable failed-break/reversal information.

**Shared PIT context measured in the same successor run:**

- broad-market alignment: bounded prior-session/intermediate market trend, realized-volatility state, and same-day market move through signal time where reconstructable;
- ticker relative strength/weakness versus SPY on a small preregistered set of horizons; sector-relative strength only after an accepted PIT sector map;
- one bounded higher-timeframe trend representation for intraday setups;
- trend maturity/extension, initially distance from a medium-term reference in ATR units and move already traveled before entry relative to normal ATR/volatility;
- volume/participation as an independent evidence family: opening RVOL, premarket RVOL, dollar volume, same-time historical participation and breakout/retest/reclaim participation where PIT-safe;
- existing gap, signal-time, price-band, realized-volatility, liquidity and execution-quality context.

Context variables are not universal gates. B36 first measures their standalone/incremental explanatory value, then only economically coherent interactions, under rolling/walk-forward evidence and multiplicity control. Confluence is evaluated **after** standalone strategy results as a separate ranking/eligibility layer across materially distinct evidence families: price structure/setup, participation, broad-market state, ticker relative strength, higher-timeframe state, volatility/liquidity and later event/fundamental context where appropriate. Correlated indicators are not independent votes.

**Deferred from B36 strategy evidence:** sector-relative strength until source mapping is PIT-valid; anchored VWAP until anchors are objectively defined; fundamentals for intraday ORB; Level-2/order-book, options-flow and dealer-gamma/GEX mechanisms until their own historical source contracts exist; portfolio daily-loss limits, capital competition, strategy exposure, concentration and correlation admission rules until account/PAPER replay. Fixed arbitrary stop percentages/targets, human psychology rules, discretionary small watchlists, Fibonacci/ICT/FVG/order-block terminology and generic indicator stacks are not added merely from practitioner discussion.

**Evaluation objective:** improve economically viable condition coverage without sacrificing confidence. Report win rate together with payoff ratio, net expectancy/net-R, drawdown/tail loss, cost sensitivity, support, fold/year stability, concentration, MFE/MAE, holding time and abstention. A higher win rate with worse expectancy or tail risk is not an improvement. No dense optimization sweep is authorized; by default no more than three materially distinct successor candidates per family per research cycle.
''')
ROADMAP.write_text(roadmap, encoding='utf-8')

register = REGISTER.read_text(encoding='utf-8')
register = replace_once(
    register,
    '**Final robustness component:** PR #79 implements the five frozen minute-path perturbation families in one DEVELOPMENT-only pass.',
    '**Final robustness component:** PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the workstation run remains pending. It implements the five frozen minute-path perturbation families in one DEVELOPMENT-only pass.',
    'register PR79 state',
)
register = append_once(register, '## 7. Successor research hypotheses accepted for testing', '''
## 7. Successor research hypotheses accepted for testing

These entries are **approved research hypotheses only**. They are not strategy validation, authority promotion, or permission to reinterpret B35 v1. Exact strategy specifications and fingerprints are frozen only in the successor package after B35 targeted perturbation evidence closes.

### 7.1 `orb_stocks_in_play_5m_v1` — planned / high priority

- Family: Opening Range / opening momentum; it is not independent confluence from other ORB variants.
- Evidence source: `LITERATURE_ANCHORED` idea prior plus independent ATLAS motivation from weak unrestricted ORB and condition-sensitive B35 behavior.
- Mechanism: abnormal same-time opening participation / relative volume + sufficient executable liquidity/volatility -> first-five-minute directional range -> objective breakout -> intraday continuation.
- Must define before performance: universe/liquidity floor, same-time opening-volume baseline, finite activity-selection rule, 5-minute range, breakout confirmation, entry clock, stop/invalidation, exit/EOD flat rule, sizing and cost assumptions.
- Primary question: does activity selection transform broad negative ORB into a viable opening-momentum specialist after realistic costs?

### 7.2 15-minute ORB close + retest challenger — planned / high priority

- Family: Opening Range; versioned challenger to `b34_opening_range_breakout_15m_v1`, not a new economic family.
- Evidence source: `INTERNAL_CHALLENGER` / practitioner-motivated false-break hypothesis.
- Freeze objective close-outside-range, retest distance, retest window, hold/rejection confirmation, entry, stop, exit and no-retest handling before performance.
- Compare directly with v1 for trade-count reduction, MAE, MFE sacrificed by later entry, win rate, net expectancy/net-R, execution quality and condition stability.

### 7.3 Objective session-level failed-break/reclaim — planned / medium-high priority

- Family: Exhaustion reversal / structural failed break.
- Evidence source: `PRACTITIONER_BASELINE` with mechanism support; do not use hidden-liquidity/ICT/SMC claims.
- Initial PIT levels: previous-day high/low and premarket high/low. Opening-range levels may be a later version, not an open-ended target search.
- Freeze normalized breach depth, maximum reclaim time, confirmation, entry, sweep-extreme stop/invalidation and one coherent exit hierarchy before performance.
- Primary question: does breach-then-reclaim of universally observable session levels contain measurable reversal/continuation information after costs?

### 7.4 Shared successor context / routing evidence

Accepted for measurement in the next full historical run, not as automatic hard gates:

- broad-market directional alignment and volatility state, including same-day benchmark movement through the information-safe signal time where reconstructable;
- ticker relative strength/weakness versus SPY over a small preregistered set of economically distinct horizons;
- sector-relative strength only after a PIT-valid sector map exists;
- bounded higher-timeframe ticker trend for intraday setups;
- trend maturity/extension, initially ATR-normalized distance from a medium-term reference and fraction of normal movement already traveled before entry;
- opening/premarket/same-time volume participation and dollar-volume quality;
- overnight gap, price band, signal time, realized volatility and execution/liquidity quality already motivated by B35 diagnostics.

Confluence remains a separate layer. Standalone strategy outcomes are preserved first; then incremental evidence is measured across independent families (price structure, participation, market state, relative strength, higher-timeframe state, volatility/liquidity, and later event/fundamental context). RSI/MACD/EMA variants are not counted as independent votes merely because they are numerically different transforms of price.

### 7.5 Deferred/rejected near-term ideas

- fundamentals are deferred for intraday ORB; future swing-conditioning research may ask whether technical setups vary by PIT fundamental/event quality without reopening closed SEC alpha hypotheses;
- portfolio daily-loss limits, simultaneous-position competition, concentration, strategy exposure and capital allocation belong to account/PAPER simulation rather than independent opportunity evidence;
- anchored VWAP waits for objective anchor semantics; ordinary VWAP may remain both a shared context and a separately specified strategy mechanism;
- Level-2/order-book, options-flow and GEX require separate historical source authority;
- fixed arbitrary stop percentages/R:R, human psychology rules, small discretionary watchlists, Fibonacci and subjective ICT/FVG/order-block terminology are not adopted from the reviewed practitioner material.

### 7.6 Successor laboratory target

The next major Track-B experiment targets **19 economic strategy families**: the ten retained families plus nine distinct additions. Nearby policy variants, including the two ORB challengers, remain within their economic family for multiplicity and confluence accounting. B35 perturbation results determine which additional gap/premarket/HVD/ORB v2 challengers earn one of the bounded research slots before the successor contract is fingerprinted.

The successor objective is **economically viable condition coverage**, not maximum win rate. Qualification evidence must consider win rate, payoff ratio, net expectancy/net-R, cost decay, drawdown/tail loss, sample/support, fold/year stability, concentration, MFE/MAE, holding time and abstention. No favorable post-result slice validates itself; a frozen successor still requires untouched/prospective evidence before promotion.
''')
REGISTER.write_text(register, encoding='utf-8')

print('updated README.md, docs/roadmap.md, docs/strategy_evidence_register.md')
