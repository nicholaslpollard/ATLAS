from __future__ import annotations

from pathlib import Path


OPTION_FP = "39ab7ed68ce001b0bd663a6085c71bb62220416324eba8216db71366ecb73c22"


readme = Path("README.md")
text = readme.read_text(encoding="utf-8")

old = (
    "This record is a simulation/control-plane artifact only. It performs no provider or broker "
    "access, creates no order, and grants no PAPER, LIVE, promotion or confluence authority. "
    "Option candidates may currently be supplied only as already-formed decision-support "
    "`EconomicCandidate` objects; the separately versioned option scenario-economics adapter "
    "remains future work and historical option P&L remains unclaimed."
)
new = (
    "This record is a simulation/control-plane artifact only. It performs no provider or broker "
    "access, creates no order, and grants no PAPER, LIVE, promotion or confluence authority. "
    "Option candidates can now be produced by the separately versioned "
    "`atlas-option-scenario-economics-adapter-v1` and supplied to this unchanged decision-record "
    "contract. Historical option P&L remains unclaimed."
)
if old not in text:
    raise SystemExit("README decision-record handoff text not found")
text = text.replace(old, new, 1)

old = """The next Track A package is the separately versioned option scenario-economics
adapter using the accepted underlying move/time distribution plus explicit
strike/DTE, executable quote/spread, Greeks, IV scenario/surface context, liquidity,
and event evidence. Option capital/risk semantics may enter the account simulator
only after that economics contract is accepted. The Strategy Evidence Register is
unchanged because this package creates no new strategy evidence or disposition."""
new = f"""The separately versioned option scenario-economics adapter is now implemented
under frozen contract `{OPTION_FP}` (`atlas-option-scenario-economics-adapter-v1`). It may
produce option decision-support candidates, but option capital/risk semantics still
fail closed in the account simulator. The next Track A package is therefore an
explicit option capital/risk reservation contract; it must not reuse stock notional,
margin, or collateral assumptions. The Strategy Evidence Register remains unchanged
because this is product architecture rather than strategy evidence."""
if old not in text:
    raise SystemExit("README account-state continuation text not found")
text = text.replace(old, new, 1)

marker = "## 2026-09-16 — Option scenario-economics adapter foundation"
if marker not in text:
    text += f"""

## 2026-09-16 — Option scenario-economics adapter foundation

Track A now has a separately versioned option scenario-economics adapter under
frozen contract `{OPTION_FP}` (`atlas-option-scenario-economics-adapter-v1`). It consumes
the accepted underlying move/time forecast plus `OptionCandidateEvidence` and emits
the same `OPTION` `EconomicCandidate` consumed by the universal actionability and
trade-expression layer. V1 is intentionally bounded to long, single-leg,
direction-aligned calls for bullish forecasts and puts for bearish forecasts;
unavailable/neutral forecasts and direction-mismatched contracts do not create a
candidate.

The adapter does not manufacture an option-return distribution from sparse Greeks.
Expected, favorable, and adverse terminal option premiums plus model probability of
profit are explicit outputs of a separately identified and SHA-256-fingerprinted
scenario model, and that model must bind the exact underlying-forecast instance
fingerprint. Scenario prices must satisfy `adverse <= expected <= favorable` and the
holding period cannot exceed contract DTE. Current midpoint is the valuation
reference; entry executes economically at the ask, so the entry half-spread is
explicit. Exit slippage, commissions, and fees are explicit nonnegative costs.
Expected gross P&L is `(expected_terminal_premium - current_mid) * multiplier *
contracts`; all-in expression cost adds entry spread plus explicit exit/cash costs;
net value and return on capital remain signed and are never clamped positive.

Completeness is separately auditable across option contract evidence, delta/gamma/
theta/vega, current IV plus percentile/skew/term context, quote/open-interest/volume
liquidity, event context, and rates/dividends. Incomplete context can remain visible
as an economic candidate but fails the existing universal option gate. Upstream
option-screen rejection, unacceptable in-horizon event risk, executability failure,
and risk-budget rejection also remain explicit. A supplied reference-model premium
above the executable ask marks only `MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY`; it is
not historical option-P&L truth or independent trading authority.

The option `capital_required_dollars` value is only the economic denominator used to
compare return on capital. This package deliberately grants **no simulator option
reservation/collateral semantics**. It also performs zero provider/broker reads or
writes, creates no order, claims no historical option P&L, and grants no PAPER,
LIVE, promotion, or confluence authority. Historical option qualification still
requires accepted point-in-time option-chain/quote/IV evidence rather than synthetic
translation from stock returns.

Immediate Track A continuation is the separately versioned option capital/risk
reservation layer. It must define long-option debit/max-loss cash reservation and
option-specific exposure/accounting without mapping stock gross-notional semantics
onto options. Fill/mark-to-market/outcome authority remains a later package. The
Strategy Evidence Register is intentionally unchanged by this product-only work.
"""

readme.write_text(text, encoding="utf-8")


roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
old = """Immediate Track A continuation after acceptance:

1. implement a separately versioned option scenario-economics adapter from the same
   underlying move/time forecast plus explicit strike/DTE, executable quote/spread,
   Greeks, IV level/change/surface context, liquidity and event evidence;
2. only after that contract is accepted, define option capital/risk reservation
   semantics in the simulator; do not map stock notional/capital assumptions onto
   options;
3. add later execution/fill and mark-to-market/outcome state as separate authority
   packages rather than relabeling reservations as positions/fills;
4. expose decision fingerprints, reservation/ledger state, trade-expression mode,
   economics and rejection/abstention reasons through the existing browser/control
   plane;
5. preserve all qualifying PAPER/LIVE gates and existing broker authority boundaries."""
new = """Immediate Track A continuation after acceptance:

1. define a separately versioned long-option capital/risk reservation contract tied
   to accepted option-economics evidence, explicit debit/max-loss cash at risk, and
   option-specific exposure fields; never substitute stock notional/margin rules;
2. extend the deterministic account-state/ledger replay so accepted OPTION decisions
   can reserve and release capital under that contract while preserving exact
   decision and economics fingerprints;
3. add later execution/fill and mark-to-market/outcome state as separate authority
   packages rather than relabeling reservations as positions/fills;
4. expose decision fingerprints, reservation/ledger state, trade-expression mode,
   economics and rejection/abstention reasons through the existing browser/control
   plane;
5. preserve all qualifying PAPER/LIVE gates and existing broker authority boundaries."""
if old not in text:
    raise SystemExit("roadmap account-state continuation block not found")
text = text.replace(old, new, 1)

marker = "## Track A option scenario economics — 2026-09-16"
if marker not in text:
    text += f"""

## Track A option scenario economics — 2026-09-16

The option construction boundary is now frozen under contract
`{OPTION_FP}` (`atlas-option-scenario-economics-adapter-v1`). It consumes the accepted
underlying move/time forecast and validated `OptionCandidateEvidence`, and it emits a
normal `OPTION` `EconomicCandidate` for the already accepted universal actionability
and four-mode trade-expression gate.

V1 scientific/product semantics:

1. support only long single-leg calls for bullish forecasts and puts for bearish
   forecasts; unavailable/neutral forecasts or direction mismatch produce no option
   candidate;
2. bind every scenario model to the exact underlying-forecast fingerprint and require
   an explicit model id plus SHA-256 fingerprint;
3. require explicit expected/favorable/adverse terminal premiums and model
   probability of profit; do not infer a historical option-return distribution from
   stock returns or sparse Greeks;
4. require ordered scenario premiums (`adverse <= expected <= favorable`) and a
   holding period no longer than option DTE;
5. use current quote midpoint as valuation reference and ask debit as entry
   execution economics; derived entry half-spread plus explicit exit slippage,
   commissions and fees form all-in expression cost;
6. compute signed net value and return on explicit economic capital without clamping
   negative economics; the capital input is **not** simulator reservation authority;
7. preserve separate completeness state for contract, Greeks, IV surface/context,
   liquidity, events and rates/dividends so the universal option gate can reject
   incomplete evidence transparently;
8. make upstream option-screen failure, event-risk rejection, executability and
   risk-budget rejection auditable rather than dropping the candidate silently;
9. permit an optional reference-model premium only as model-relative valuation
   evidence; `model_reference_premium > ask` maps to
   `MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY`, never to historical support;
10. claim no historical option P&L and require a separately accepted PIT option
    source before any historical option-return qualification.

Deterministic economics use:

- entry spread cost = `(ask - mid) * contract_multiplier * contracts`;
- expected gross P&L = `(expected_terminal_premium - mid) * multiplier * contracts`;
- all-in cost = entry spread + exit slippage + round-trip commissions + fees;
- expected net value = expected gross P&L - all-in cost;
- expected return on capital = expected net value / explicit economic capital;
- favorable gain evidence = `max((favorable_terminal_premium - mid) * multiplier * contracts, 0)`;
- adverse loss evidence = `max((mid - adverse_terminal_premium) * multiplier * contracts, 0)`.

Provider reads/writes = 0, broker reads/writes = 0, order writes = 0, historical
option-P&L claim = false, simulator option-reservation authority = false, PAPER =
false, LIVE = false, promotion = false and confluence authority = false. The accepted
simulation decision-record contract needs no mutation because it already accepts
normalized option `EconomicCandidate` inputs; the new adapter supplies those inputs
with explicit provenance.

Immediate Track A continuation:

1. freeze long-option account capital/risk semantics before any option reservation is
   allowed; debit/max-loss cash-at-risk, fees and exposure measures must be explicit;
2. extend the account-state ledger with option-specific reservation/release while
   keeping stock gross notional and option exposure conceptually separate;
3. only after reservation semantics are accepted, compose adapter-produced option
   candidates through decision record -> account state in focused replay tests;
4. defer fills, mark-to-market, realized P&L and broker mutation to separately
   authorized packages;
5. expose option scenario/economic/completeness/rejection lineage in the browser
   control plane without creating a second trading truth.

The Strategy Evidence Register is intentionally unchanged because this package adds
product option-construction architecture, not new strategy evidence or a disposition
change.
"""

roadmap.write_text(text, encoding="utf-8")
