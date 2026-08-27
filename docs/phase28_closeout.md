# Phase 28 Closeout — Cross-Stock Lead-Lag & Residual Network Alpha

**Disposition:** `ACCEPTED_NEGATIVE`  
**Target closeout head:** `945adf9b2722da3822e6dcc79467ae9620d5d439`  
**Frozen policy fingerprint:** `0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`

## Plain-English phase end

Phase 28 was executed correctly, but none of the eight frozen cross-stock residual/lead-lag hypotheses earned historical analytical support. This is accepted negative scientific evidence, not a software failure and not a reason to weaken the frozen research standard.

The tested architecture asked whether observation-time moves in other production-relevant stocks could improve selection of existing bullish/bearish candidates after removing same-session common movement. The answer under the preregistered 3-session horizon, fixed 20% tails, 10 bps primary / 25 bps stress economics, chronological selection/internal split, dependence-aware statistics, robustness gates, and global Holm correction was no.

## Target-machine evidence

The target research run at pre-closeout head `2eea81855803faddbfc7d07109d3af02a799f430` returned:

- development network rows: **14,466**;
- protected network predictor rows: **741**;
- selection survivors: **0**;
- selection winners: **0**;
- internal-validation finalists: **0**;
- protected-confirmed supported candidates: **0**;
- protected candidate rows queried: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0 / 0 / 0 / 0 / 0**;
- cumulative runner: **PASS**.

The final target closeout at `945adf9b2722da3822e6dcc79467ae9620d5d439` returned:

- `Phase 28 closeout: PASS`;
- `Disposition: ACCEPTED_NEGATIVE`;
- development network rows: **14,466**;
- protected network predictor rows: **741**;
- selection survivors/winners/finalists/supported candidates: **0 / 0 / 0 / 0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- end-to-end anti-workaround audit: **True**;
- Phase 29 signal-to-trade entry satisfied: **False**;
- provider/broker/order/PAPER/LIVE activity: **0 / 0 / 0 / 0 / 0**;
- `Pass: True`.

## Scientific conclusion

Phase 28 rejected the tested residual-momentum, one-day peer-lead, five-day peer-lead, and diffusion-gap hypotheses in both LONG and SHORT directions under the frozen standard. No candidate may be promoted as a Phase 28-supported alpha merely because it was the least negative, closest to a threshold, or visually attractive.

The network window, leader count, peer-selection rules, signal formulas, tail fraction, cost assumptions, outcome horizon, chronology, confidence thresholds, robustness gates, and multiplicity treatment remain frozen historical provenance and must not be retuned after this result to manufacture support.

## Protected evidence state

The inherited `2026-05-12` through `2026-08-11` protected predictor holdout remains outcome-unopened. Phase 28 had zero finalists, so the confirmation path exited before any read plan or future-return query. This means the holdout remains available only to a later separately preregistered alpha phase while the zero-read state remains independently provable.

The first future protected-outcome read permanently consumes that holdout for subsequent strategy/model selection.

## Architecture and authority conclusion

`docs/phase28_end_to_end_anti_workaround_audit.md` records a PASS. The Phase 28 branch adds research/backtesting authority only and does not modify discovery, portfolio, risk, execution, broker, or browser/control-plane runtime authority. Historical analytical support remains empty, automatic broker failover remains disabled, and PAPER/LIVE authority remains unchanged.

## Downstream consequence

The existing signal-to-trade construction gate remains blocked because ATLAS still has zero accepted historically `SUPPORTED` alpha. Phase 28 acceptance therefore grants no downstream trading authority.

The next numbered phase must be separately preregistered and materially different from the failed Phase 26 deterministic/composite self-feature search, Phase 27 same-stock cross-sectional learning/ranking search, and Phase 28 cross-stock residual/lead-lag network search. Negative evidence is preserved rather than repaired into a positive result.
