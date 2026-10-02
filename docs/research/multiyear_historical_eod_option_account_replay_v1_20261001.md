# Multiyear historical EOD option account replay V1 — 2026-10-01

## Scope

This is the first receipt-bound modeled historical option account replay over the
accepted 2021–2025 ATLAS daily-LONG signal cohort. It is deliberately separate from
`multiyear_offline_account_replay_v1`, whose source origin remains synthetic fixtures
only.

V1 does not grant historical fill/P&L authority. It produces a modeled historical EOD
scenario from immutable source receipts and the causal admission audit.

## Population

The causal admission audit accepted 10,809 dated case/right source shapes at entry,
from 20,040 dated rights over the original 14,902 stock-signal cases. The previous
8,574 count required both entry and the initially frozen later exit source and is not
used as an entry denominator.

V1 preserves the full 14,902 original case denominator. CALL is the direction-aligned
primary option mode because the accepted source cohort is daily LONG. PUT is retained
as a separately reported counterfactual diagnostic. The engine never switches a case
between CALL and PUT based on future liquidity, price or return.

## Entry

Entry requires the already signed causal-admission result. The observed ask comes
from the exact EOD probe snapshot and must still match the SHA-verified quote body.
Entry is at the documented 16:00 ET snapshot and requires the already frozen entry
clock/liquidity source shape.

The multiplier is 100 only under the provider-standard modeled-contract assumption
established by the admission audit. Independent OCC deliverable/multiplier proof
remains false.

## Exit policy

After a position has been causally admitted, V1 reopens the same SHA-verified physical
quote history and advances chronologically. The first later row qualifies as a modeled
exit only when all of these hold:

- session is strictly after entry;
- session is strictly before expiration;
- session is before 2026-01-01;
- `updated` is exactly 16:00 ET;
- quote is two-sided;
- displayed bid size is at least one contract;
- reported option volume is positive;
- same-row `underlyingPrice` is present; and
- bid is positive.

The modeled exit uses that bid. If the first later source row is unqualified, later
rows are considered only when their date arrives; no future exit property influences
entry. If no qualified pre-expiry/pre-2026 exit exists, the position remains open and
unmarked. It consumes cash, reserved exit fee and account position capacity rather
than disappearing from the backtest.

## Account mechanics

V1 reuses `ReplayPolicy` settings while retaining a separate historical adapter:

- initial cash default $100,000;
- default 10% of available cash per position;
- default maximum five open positions;
- cash-only long contracts;
- ask plus configured per-share slippage on entry;
- bid minus configured per-share slippage on exit;
- default $0.65 fee per contract on entry and exit;
- future exit fee reserved before admitting a new position;
- exits process before entries at an identical timestamp; and
- no terminal equity/return is reported if unresolved open positions remain.

## Authority boundary

The output may report modeled realized cash/P&L for completed EOD round trips. It does
not claim that the historical provider snapshot was actually executable for ATLAS,
does not verify an independent OCC deliverable, does not read protected 2026 outcomes,
and does not change strategy evidence, PAPER, LIVE or promotion state.

## First workstation gate

After exact-head CI and merge, run the historical EOD option replay against the
immutable causal-admission audit. The command will build the receipt-bound scenario
and run CALL primary plus PUT counterfactual in one zero-provider pass.
