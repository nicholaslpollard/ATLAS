# Literature-Anchored Alpha Exploration

**Branch:** `literature-anchored-alpha-exploration`  
**Base main SHA:** `34343fff92de87241c20f57f0c783fa8409fc6a1`  
**Status:** EXPLORATORY / NON-AUTHORITATIVE  
**Created:** 2026-09-01

## Purpose

This branch is a deliberately isolated research track for testing alpha mechanisms that were specified, documented, or independently replicated outside ATLAS before ATLAS evaluates them.

It exists alongside, not instead of, the main ATLAS alpha-discovery program. The main program may continue designing original strategies and mechanisms. This branch asks a separate question:

> Can ATLAS reproduce or improve externally documented return-predictive mechanisms under ATLAS point-in-time, cost, leakage, multiplicity, robustness, and protected-holdout standards?

External literature is a hypothesis prior only. A published or replicated mechanism is **not** ATLAS `SUPPORTED` evidence and grants no trading authority.

## Hard isolation boundary

Until a later explicit operator decision, this branch may not:

- reclassify any historical ATLAS accepted-negative result;
- change `docs/roadmap.md` entry conditions or Phase33 authority;
- consume the master protected outcome window;
- change production discovery thresholds, WARM/HOT persistence, regime routing, strategy routing, risk authority, AI authority, execution planning, PAPER authority, LIVE authority, or broker behavior;
- grant PAPER/LIVE authority from literature evidence alone;
- merge experimental behavior into `main` automatically;
- reinterpret a literature replication as validation of an existing ATLAS strategy merely because the economic labels are similar.

Research code should be additive and preferably live under backtesting/research namespaces, scripts, tests, and branch-specific documentation.

## Scientific sequence

Each mechanism follows this order:

1. **External specification audit** — identify the original/replicated definition, direction, formation period, portfolio period, universe filters, and evidence quality.
2. **ATLAS source feasibility** — prove the required predictor inputs can be reconstructed point-in-time without target/protected outcome access.
3. **Native population census** — measure the complete eligible cross-section before ATLAS discovery/routing filters.
4. **Research-gate calibration** — use the retained `research_gate_calibration`, `research_population_coverage`, and `research_gate_freeze` safeguards before outcome access.
5. **Prospective freeze** — freeze signal formula, universe, chronology, costs, weighting/ranking, holding period, multiplicity family, robustness requirements, sample/effective-sample rationale, and protected policy.
6. **Development outcomes** — evaluate the native characteristic first.
7. **ATLAS layer attribution** — only if the native signal contains evidence, separately test whether ATLAS regime/discovery/context layers improve, preserve, or destroy it.
8. **Protected outcome** — open only for a predeclared finalist satisfying all prior gates.
9. **Adoption decision** — even a `SUPPORTED` experimental result does not modify production automatically; integration requires a separate explicit proposal and operator decision.

## Native-signal-first rule

Literature-backed characteristics are not initially forced through the Phase25 WARM/HOT production funnel.

The first scientific question is whether the documented characteristic contains return-predictive information in the broad ATLAS point-in-time eligible universe. Continuous characteristics should normally expose the full cross-sectional relationship (for example, quantiles and monotonicity), not only a hand-picked trigger threshold.

If a native signal works, ATLAS filters may then be tested as an **attribution experiment**. This separates:

- `ECONOMIC_SIGNAL_ABSENT`, from
- `UPSTREAM_FILTER_DESTROYED_SIGNAL`, from
- `ATLAS_CONTEXT_IMPROVED_SIGNAL`.

## Initial candidate registry

### Candidate LIT-01 — Heston-Sadka return seasonality, years 2–5

**Priority:** first feasibility target.  
**Data class:** price-only.  
**Mechanism density:** cross-sectional monthly.  
**External specification:** average return in the same calendar month over the preceding 2–5 years; higher signal predicts higher next same-calendar-month relative return.  
**External replication anchor:** OpenSourceAP `MomSeason`, classified `1_clear` original predictability / `1_good` replication quality, Heston and Sadka (2008). OpenSourceAP documents an equal-weighted decile long-short implementation and a one-month portfolio period.  
**Why first:** it is materially different from ordinary momentum and ATLAS trigger-based pullback/reversal logic, needs no new fundamental/event source, and can be reconstructed from chronology-safe historical price data already central to ATLAS.

Reference anchors:

- Heston, Steven L. and Ronnie Sadka, “Seasonality in the Cross-Section of Stock Returns,” *Journal of Financial Economics* 87(2), 2008, DOI `10.1016/j.jfineco.2007.02.003`.
- OpenSourceAP/CrossSection `SignalDoc.csv`, `MomSeason`: “Average return in the same month over the preceding 2-5 years.”

**Current status:** source-feasibility design permitted; target outcomes remain closed.

### Candidate LIT-02 — industry-adjusted short-term reversal

**Priority:** high, pending PIT industry-source proof.  
**Data class:** price + industry classification.  
**External specification:** recent stock return minus recent mean return of its industry; buy the strongest relative underperformers and sell the strongest relative outperformers.  
**Recent evidence:** Stosik and Zaremba (2026), *Economics Letters* 267, 113113, DOI `10.1016/j.econlet.2026.113113`, reports that industry adjustment revives short-term reversal across 64 markets and improves net results relative to conventional reversal.

**PIT warning:** ATLAS’s retained bulk Massive reference snapshots do not contain SIC/industry fields. Massive’s Ticker Overview endpoint exposes `sic_code`, but its documentation states that the historical `date` view can use SEC information according to the filing period-of-report rather than filing availability. That creates a potential decision-time leakage problem and must be resolved before this mechanism can freeze.

**Current status:** parked at source-feasibility boundary; no outcome access.

### Candidate LIT-03 — literature-characteristic composite

**Priority:** later, only after individual characteristics are reconstructed cleanly.  
**Purpose:** test a small preregistered ensemble of externally specified characteristics instead of assuming every weak effect must earn standalone authority.

This candidate may not be formed adaptively from whichever LIT-01/LIT-02 variants happen to look best. Inputs, transforms, model class, training policy, multiplicity treatment, and evaluation must be frozen prospectively as a new experiment.

## Candidate queue retained for later feasibility

- corporate investment / asset growth / financing characteristics;
- options-implied information signals if historical option-data entitlement supports PIT reconstruction;
- dividend seasonality;
- economically linked customer-supplier momentum if a defensible PIT relationship source is available.

Form 4, Schedule 13D/13G, SEC XBRL quality/accruals, FINRA short interest, 8-K event families, SEC earnings innovation, and the closed Form 13F v1 lineage remain historical ATLAS evidence and are not silently repackaged here.

## First branch action

Proceed with **LIT-01 source-only feasibility** before any target-return read. The source stage should answer only:

- Do canonical daily price histories span enough years to form the 2–5-year same-calendar-month predictor?
- How many eligible instrument-month predictor rows can be reconstructed in DEVELOPMENT and in the protected period without opening protected target outcomes?
- How complete is the point-in-time identity/universe mapping?
- What are the natural cross-sectional counts per formation month?
- What sample/effective-sample floors are defensible before freezing science?

If source capacity is insufficient, close LIT-01 as a source-capacity result and move to the next materially different candidate. Do not inspect forward returns to decide whether to repair or resize the experiment.
