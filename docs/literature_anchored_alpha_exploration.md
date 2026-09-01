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

Research code is additive and lives in branch-specific backtesting modules, scripts, tests, documentation, and derived research caches.

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

The first scientific question is whether the documented characteristic contains return-predictive information in the broad ATLAS point-in-time eligible universe. Continuous characteristics should normally expose the full cross-sectional relationship, including quantiles and monotonicity, rather than only a hand-picked trigger threshold.

If a native signal works, ATLAS filters may then be tested as an **attribution experiment**. This separates:

- `ECONOMIC_SIGNAL_ABSENT`, from
- `UPSTREAM_FILTER_DESTROYED_SIGNAL`, from
- `ATLAS_CONTEXT_IMPROVED_SIGNAL`.

## Candidate LIT-01 — Heston-Sadka calendar-month return seasonality

**Priority:** active first feasibility target.  
**Data class:** historical stock returns + stable PIT identity + corporate actions.  
**Mechanism density:** cross-sectional monthly.  
**Target outcomes:** CLOSED.

The source-only family contains exactly two externally specified hypotheses, both documented before ATLAS target-return access:

1. `momseason_short_year1` / OpenSourceAP `MomSeasonShort` — the stock's return in the same calendar month one year earlier;
2. `momseason_years2_5` / OpenSourceAP `MomSeason` — the average stock return in the same calendar month two through five years earlier.

Both have positive direction, a one-month portfolio period, and OpenSourceAP classifications `1_clear` original predictability / `1_good` replication quality. They form one two-hypothesis family; later performance multiplicity must account for both. ATLAS may not inspect returns and then silently choose whichever variant looks better.

Reference anchors:

- Heston, Steven L. and Ronnie Sadka, “Seasonality in the Cross-Section of Stock Returns,” *Journal of Financial Economics* 87(2), 2008, DOI `10.1016/j.jfineco.2007.02.003`.
- OpenSourceAP/CrossSection `SignalDoc.csv`: `MomSeasonShort` and `MomSeason`.

### LIT-01 source fidelity

ATLAS canonical stock flat-file prices are not sufficient by themselves for a literature-faithful monthly return:

- the retained Massive flat-file source is unadjusted for splits and dividends;
- the literature characteristic is a return characteristic, so corporate actions cannot be ignored;
- historical ticker text cannot be assumed to represent the same security across years.

The branch therefore uses a **research-only source cache**:

- point-in-time historical Massive stock reference snapshots at the required month-end dates;
- ATLAS `InstrumentIdentityResolver` to bind historical ticker rows to the same stable security identity used at formation;
- Massive split and dividend sources for total-return source reconciliation;
- canonical daily month-end prices only for lagged predictor months.

No target-month price endpoint is permitted during source feasibility.

### LIT-01 source-capacity finding

The first source acquisition completed all 109 required historical PIT reference periods and proved broad lagged-predictor price/identity capacity without reading a target or protected return. Massive corporate-action acquisition also completed, but 82,613 dividend rows lacked `historical_adjustment_factor`.

That finding is not treated as permission to ignore dividends, delete affected rows, or weaken the signal definition. It triggers a separate source-semantics audit.

### Dual-provider total-return architecture

LIT-01 now uses an additive **Massive + Alpaca** source design rather than rebuilding the accepted ATLAS market lake or mixing provider-specific fields in the same raw table.

Provider responsibilities are separated:

- **Massive** remains the accepted point-in-time identity/reference source, the retained canonical raw market source, and one corporate-action evidence source.
- **Alpaca** is added as a secondary research-only historical source for corporate-action reconciliation and explicitly requested `raw` versus `adjustment=all` daily bars.
- **ATLAS derived data** will become the provider-neutral consumer interface only after the two-provider semantics audit is accepted. Strategies should ultimately consume a versioned total-return dataset rather than provider-specific adjustment behavior.

The accepted global Alpaca configuration remains `adjustment: raw`. Research requests use explicit per-call adjustment overrides; no existing canonical or provider data is rewritten.

Exact Alpaca response bytes are retained under an isolated provider namespace:

`data/provider/alpaca/literature_momseason_total_return/raw`

This keeps the accepted historical-backfill namespace unchanged while retaining reproducible source provenance for the experiment.

### Pre-target total-return source audit v1

The first Alpaca audit was intentionally bounded before any bulk adjusted-history reconstruction.

- Every Alpaca price case ended no later than **2021-08-31**.
- The first LIT-01 formation/target month is **2021-09**, so the audit could not inspect a LIT-01 development target month.
- The audit sampled Massive dividends with missing adjustment factors, Massive dividends with factors, and Massive splits across the safe historical interval.
- Each price case requested both literal-symbol `raw` and `adjustment=all` Alpaca daily bars and retained exact source payload hashes.

The first real target-machine run completed on exact branch head `5fcb3733d2090be4aa44660349485192b4a0cc8c` with status `TOTAL_RETURN_SOURCE_AUDIT_READY_FOR_REVIEW`:

- Alpaca corporate actions: **144,794** normalized rows;
- selected price cases: **26**;
- complete raw/all price cases: **9**;
- exact Alpaca corporate-action matches among the selected cases: **10**;
- provider-value relative error across matched cases: median **0.0**, maximum **0.2148610855404469**;
- adjustment-scale relative error across complete cases: median **0.00010431426875107088**, maximum **0.0004481352965559626**;
- missing-factor dividends: 12 selected, 2 action matches, **0 complete price cases**;
- with-factor dividends: 6 selected, 4 action matches, 5 complete price cases;
- splits: 8 selected, 4 action matches, 4 complete price cases;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- canonical data mutation, global Alpaca adjustment mutation, broker reads, order writes, PAPER submits, and LIVE writes: **none**.

The complete cases provide strong evidence that Alpaca `adjustment=all` behaves consistently with local split/dividend adjustment mathematics where both providers cover the same symbol/event. However, v1 cannot close the missing-factor question because its deterministic all-Massive sample mixed provider-domain coverage with adjustment semantics: the missing-factor cohort had no complete raw/all price case. That is a source-design limitation, not evidence that the adjustment mathematics failed.

V1 remains preserved as evidence; its selection/result is not rewritten.

### Pre-target total-return source audit v2

V2 is additive and repairs the v1 source-design limitation before any target return is opened.

Its rules are frozen before v2 adjusted-price acquisition:

1. Build the full safe-period Massive corporate-action population.
2. Build an Alpaca action index by **exact action type + literal ticker + event date** using the already-retained pre-target corporate-action cache.
3. Partition each Massive action family into exact provider overlaps and provider non-overlaps **before any adjusted price is inspected**.
4. Select the adjustment-validation cases deterministically and evenly across time from the exact-overlap population. Non-overlaps remain a separate coverage diagnostic and are never reclassified as adjustment failures.
5. Query Alpaca historical bars with `asof=<event date>` rather than `asof=-`. Alpaca documents `asof` as the entity/symbol mapping date; this preserves historical source identity while allowing provider-supported name-change mapping.
6. For dividends, use Massive `cash_amount` — the original per-share payment — with event-era raw prices. Massive `split_adjusted_cash_amount` is current-share-basis evidence and remains diagnostic only.
7. Compute two independent expected event scale changes: one from the **Massive original cash amount/split ratio** and one from the **Alpaca action value**. Alpaca `adjustment=all` is then compared with both. A blank Massive cumulative `historical_adjustment_factor` is therefore not filled from Alpaca and does not make the test circular.
8. Preserve the same hard bar barrier: no price after **2021-08-31**, zero LIT-01 target/protected returns, and no production/broker authority changes.

The v2 goal is specifically to determine whether Massive's original corporate-action values are sufficient to construct provider-neutral total returns even when Massive omits its cumulative historical adjustment factor. No tolerance is silently chosen from LIT-01 target returns; target outcomes remain closed.

Only after v2 establishes defensible semantics may ATLAS freeze the provider-neutral total-return materialization contract and scale the same source logic into a permanent historical daily/monthly total-return dataset.

### LIT-01 temporal capacity finding

The existing master protected window is `2026-05-12..2026-08-11`. A one-calendar-month mechanism has only:

- June 2026 — complete protected target month;
- July 2026 — complete protected target month;
- August 2026 — predictor can form, but the target month is incomplete at the protected-window end.

May 2026 crosses the protected-start boundary and is treated as purge/boundary evidence, not as a protected month.

The LIT-01 source policy freezes **12 independent complete protected calendar months** as the minimum protected temporal capacity, one full calendar cycle, before any target return is opened. Therefore the existing master holdout has **2 / 12** complete independent months and cannot by itself grant LIT-01 final `SUPPORTED` authority.

This does **not** prevent development or internal out-of-sample research. If LIT-01 becomes a legitimate internal finalist, a sufficiently long new protected window must be reserved prospectively rather than weakening the monthly independence requirement.

### LIT-01 implementation

Branch-only or branch-extended files include:

- `packages/backtesting/literature_momseason_policy.py`
- `packages/backtesting/literature_momseason_source.py`
- `packages/backtesting/literature_momseason_feasibility.py`
- `packages/backtesting/literature_momseason_total_return_source.py`
- `packages/backtesting/literature_momseason_total_return_source_v2.py`
- `packages/providers/alpaca/client.py` — backward-compatible explicit historical-bar query overrides;
- `packages/data/alpaca_backfill_storage.py` — backward-compatible isolated raw-source namespaces;
- `scripts/run_literature_momseason_source_feasibility.py`
- `scripts/run_literature_momseason_total_return_source_audit.py`
- `scripts/run_literature_momseason_total_return_source_audit_v2.py`
- `tests/unit/test_literature_momseason.py`
- `tests/unit/test_literature_momseason_total_return_source.py`
- `tests/unit/test_literature_momseason_total_return_source_v2.py`
- `.github/workflows/literature-alpha-exploration-tests.yml`

All LIT-01 source runners record zero target outcome reads, zero protected return reads, zero broker/order/PAPER/LIVE writes, and do not alter production state.

## Candidate LIT-02 — industry-adjusted short-term reversal

**Priority:** high, pending PIT industry-source proof.  
**Data class:** price + industry classification.  
**External specification:** recent stock return minus recent mean return of its industry; buy the strongest relative underperformers and sell the strongest relative outperformers.  
**Recent evidence:** Stosik and Zaremba (2026), *Economics Letters* 267, 113113, DOI `10.1016/j.econlet.2026.113113`.

**PIT warning:** ATLAS's retained bulk Massive reference snapshots do not contain SIC/industry fields. Massive Ticker Overview exposes `sic_code`, but historical SEC-derived fields may be associated with filing period-of-report rather than actual filing availability. That is not automatically decision-time PIT safe.

**Current status:** parked at source-feasibility boundary; no outcome access.

## Candidate LIT-03 — literature-characteristic composite

**Priority:** later, only after individual characteristics are reconstructed cleanly.

The purpose is to test a small preregistered ensemble of externally specified characteristics instead of assuming every weak effect must earn standalone authority. It may not be formed adaptively from whichever LIT-01/LIT-02 variants happen to look best. Inputs, transforms, model class, training policy, multiplicity treatment, and evaluation must be frozen prospectively as a new experiment.

## Candidate queue retained for later feasibility

- corporate investment / asset growth / financing characteristics;
- options-implied information signals if historical option-data entitlement supports PIT reconstruction;
- dividend seasonality;
- economically linked customer-supplier momentum if a defensible PIT relationship source is available.

Form 4, Schedule 13D/13G, SEC XBRL quality/accruals, FINRA short interest, 8-K event families, SEC earnings innovation, and the closed Form 13F v1 lineage remain historical ATLAS evidence and are not silently repackaged here.

## Immediate branch action

Run the **LIT-01 Massive/Alpaca total-return source audit v2**.

The stage now answers only:

- how much of each Massive corporate-action family has exact Alpaca action overlap versus provider-domain non-overlap;
- whether a deterministic sample of overlapping missing-factor dividends has complete Alpaca raw/all price evidence;
- whether Massive's original `cash_amount` or split ratio independently explains Alpaca's observed `raw` versus `adjustment=all` scale change;
- whether provider-value discrepancies are isolated outliers or a systematic semantic mismatch;
- whether the existing Massive + Alpaca sources are sufficient to freeze a provider-neutral total-return materialization contract.

The audit reads no LIT-01 target-month or protected return. A full adjusted-history backfill, research-gate calibration, prospective experiment freeze, and development outcomes remain downstream of an accepted source-semantics result.
