# Continuous Dynamic Exit V2 option replay — 2026-10-02

## Motivation

Dynamic Exit V1 correctly preserved walk-forward causality but combined entry veto
and exit-policy selection. Over the 2021–2025 target cohort it selected only 354 of
14,733 eligible cases (2.40%), all with the 3% stop / 5% target action and all in
2025. The 93 source-ready option pairs had mean modeled return on premium -11.56%,
median -19.30% and 27.96% positive. This is useful evidence about V1, but it does
not exercise a broadly dynamic exit across the five-year cohort.

V2 separates entry selection from exit parameterization. Existing accepted LONG
opportunities remain the entry population; V2 assigns each eligible case a continuous
stop and target using strictly-prior training-cell evidence already attached to that
opportunity.

## Frozen V2 formula

For each case:

- `downside_p25 = max(0, -training_p25_gross_return)`;
- `upside_p75 = max(0, training_p75_gross_return)`;
- `downside_anchor = (training_mean_mae + downside_p25) / 2`;
- `upside_anchor = (training_mean_mfe + upside_p75) / 2`;
- stop = downside anchor clipped to 1%–3%;
- target = upside anchor clipped to 2%–5%;
- if necessary, target is raised within the 5% ceiling so target >= 1.5 × stop.

The 1–3% / 2–5% bounds and 1.5x minimum reward/risk constraint retain the previously
researched static envelope while allowing continuously varying case-specific levels.

## Causality

`training_mean_mae`, `training_mean_mfe`, P25 and P75 are computed from the selected
opportunity's training-only cell. Its training cutoff precedes the signal session.
Current-case gross return, current-fold outcome, option entry price, option exit price
and future option-source availability are not inputs to stop/target derivation.

## Historical option mapping

The underlying daily path is resolved with the case-specific stop/target and the
existing conservative STOP/TARGET/TIME rules. Option entry remains the first accepted
later-session EOD ask. If the stock strategy exits before or on that option-entry
session, no option trade is admitted. Otherwise the option exit attempt uses only the
qualified EOD bid on the exact stock exit session. Missing or illiquid exact-session
evidence remains unresolved and never slides forward.

Signals whose five-session horizon would cross into 2026 stay withheld. Provider
requests remain zero.

## Outputs

V2 reports:

1. the distribution of derived stop and target values across the full eligible cohort;
2. exact-session source readiness and timing gaps by year;
3. a paired-observation diagnostic across all source-ready entry/exit pairs, explicitly
   conditional on future exit-source availability and not a causal portfolio; and
4. the same strict cash account where unresolved exits retain capital and position
   capacity.

No historical-fill, independent deliverable, strategy-promotion, PAPER or LIVE
authority is created.
