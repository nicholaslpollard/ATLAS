# Continuous Dynamic Exit V2 Closeout — 2026-10-02

## Status

**COMPLETE DIAGNOSTIC / EXIT-GEOMETRY BRANCH CLOSED / NO PROMOTION**

The first immutable workstation run of Continuous Dynamic Exit V2 completed with zero
provider requests and zero protected-2026 outcome reads. This closeout records the
observed result without creating another exit version.

## Accepted observed result

Population: 14,733 usable selected daily-LONG cases through 2025-12-23; 109 additional
selected daily-LONG cases lacked sufficient strictly-prior path evidence.

Continuous parameter distribution:

- stop minimum 2.6853%; P25 3.00%; median 3.00%; mean 2.9986%; P75 3.00%; maximum 3.00%;
- target minimum/P25/median/mean/P75/maximum **all 5.00%**.

Therefore the target parameterizer saturated at the frozen 5% ceiling for every case,
and at least 75% of stop choices sat at the frozen 3% ceiling. V2 did not produce a
materially broad continuous exit surface; operationally it converged very closely to
the already studied 3% STOP / 5% TARGET geometry.

Source-ready exact-session CALL pairs: 2,055.

Paired modeled premium diagnostics:

- mean return on premium: **-14.06%**;
- median return on premium: **-18.42%**;
- probability positive: **30.61%**;
- mean modeled P&L per contract: **-$75.01**;
- median modeled P&L per contract: **-$47.30**.

Every calendar-year paired mean was negative: 2021 -12.64%, 2022 -22.89%,
2023 -18.06%, 2024 -8.37%, and 2025 -8.88%.

The strict causal account admitted 84 positions, completed 74, retained ten unresolved
positions, ended with $24,997.70 cash and reported modeled realized P&L -$33,365.40.
Ending equity and total return remain NULL because unresolved positions are unmarked.

## Clock-boundary finding

3,230 otherwise modeled cases had a stock STOP/TARGET/TIME exit session that was not
after the accepted historical EOD option-entry session. This is a separate problem
from exit geometry: the EOD option representation can become available only after the
underlying strategy has already completed its economic trade horizon.

A zero-provider follow-up diagnostic is therefore authorized to quantify stock-decision
to EOD-option-entry lag, underlying movement before option entry, contract moneyness
migration, and the exact fraction of causal EOD option entries arriving after the
underlying strategy exit.

## Research disposition

Do **not** create Continuous Exit V3, widen the stop/target bounds, weaken causal
selection, or tune another exit formula from the same DEVELOPMENT outcomes.

The next research bottleneck is entry/trade-expression fidelity:

1. quantify historical EOD option-entry clock translation;
2. separate underlying signal expectancy from derivative expression;
3. require an option source at the intended decision clock before treating an option
   replay as the same economic strategy;
4. later evaluate STOCK vs OPTION through the existing trade-expression/economic gate;
5. treat PIT-safe news as an incremental evidence layer rather than assumed alpha.

No historical-fill authority, strategy promotion, qualifying PAPER, or LIVE authority
is created by this closeout.
