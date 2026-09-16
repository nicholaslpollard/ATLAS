from __future__ import annotations

from pathlib import Path


def append_once(path_text: str, marker: str, section: str) -> None:
    path = Path(path_text)
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + section.rstrip() + "\n", encoding="utf-8")


append_once(
    "README.md",
    "## 2026-09-16 — Stock economics adapter foundation",
    '''## 2026-09-16 — Stock economics adapter foundation

Track A now has a deterministic underlying-forecast-to-stock-economics adapter under frozen contract `68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924` (`atlas-stock-economics-adapter-v1`). It consumes the accepted `atlas-underlying-move-time-forecast-v1` object and produces the `STOCK` `EconomicCandidate` already consumed by the universal trade-expression/actionability gate. Unavailable or neutral forecasts do not create a stock candidate.

The adapter deliberately keeps every economic assumption explicit. Position notional and capital reserved are separate inputs; no leverage, margin or collateral rule is inferred. Entry/exit slippage, round-trip commissions/fees, horizon borrow cost and horizon financing cost are supplied as explicit nonnegative inputs. Expected gross P&L is the direction-adjusted mean signed underlying return times position notional; expected net value subtracts all-in expression cost; expected return on capital divides net value by explicitly reserved capital. Forecast MFE/MAE scale expected gain/loss evidence. Net probability of profit is an explicit post-cost scenario input and cannot exceed the forecast's gross directional sign probability. The candidate preference score is expected return on capital, so negative economics remain negative rather than being clamped or rescued.

Bearish stock construction also carries an explicit shortability input. If the stock is not shortable, the economic candidate is preserved with `executable=false` so the downstream gate can explain the rejection. The adapter performs no provider/broker reads or writes, chooses no order quantity, creates no order, and grants no PAPER, LIVE, option-trading, confluence or promotion authority.'''
)

append_once(
    "docs/roadmap.md",
    "## Track A stock-economics adapter foundation — 2026-09-16",
    '''## Track A stock-economics adapter foundation — 2026-09-16

The product-side decision path now includes a frozen stock-economics adapter after the accepted underlying move/time forecast contract and before universal actionability/trade-expression selection.

Frozen adapter contract: `68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924` (`atlas-stock-economics-adapter-v1`).

Decision sequence:

`strategy/forecast evidence -> underlying move/time forecast -> explicit stock economics -> universal economic gate -> trade-expression mode -> stock/option/abstain -> portfolio/risk -> simulator/execution boundary`

Stock economics v1 rules:

1. Only an available directional underlying forecast can create a stock candidate; unavailable and neutral forecasts abstain at this layer.
2. Position notional and reserved capital are explicit independent inputs. The adapter never infers leverage, margin, buying power or short collateral.
3. Entry/exit slippage bps, round-trip commissions/fees, horizon borrow cost and horizon financing cost are explicit nonnegative inputs. All are included in `execution_cost_dollars` as all-in expression cost for conservative actionability comparison.
4. Direction-adjusted mean underlying return drives expected gross P&L. All-in cost is subtracted to obtain expected net value, and net value divided by reserved capital gives expected return on capital.
5. Forecast mean MFE/MAE times position notional provide the candidate's expected gain/loss path-scale evidence. They are not option P&L claims.
6. Net probability of profit is supplied explicitly by the stock scenario layer; it is never inferred from MFE or threshold-touch rates and cannot exceed the forecast's gross directional sign probability.
7. Candidate preference score is expected return on capital. Negative expected value/ROC is preserved and therefore fails the downstream economic gate rather than being clamped positive.
8. Bearish stock candidates require explicit shortability. A failed shortability check keeps the candidate for audit but marks it non-executable.
9. This package remains broker-neutral decision support. Provider reads/writes, broker reads/writes, order creation, PAPER, LIVE, strategy promotion and confluence authority remain false/unavailable.

Immediate Track A continuation after acceptance:

1. compose the move/time forecast, stock-economics adapter and trade-expression gate into one deterministic product decision record with complete reason-code lineage;
2. feed that record into the account simulator without touching the legacy Phase 13 equity-only case contract or Phase 15 execution-authority contract;
3. add stock portfolio/capital reservation effects to simulation using explicit account-state inputs;
4. implement a separately versioned option-scenario economics adapter using strike/DTE/Greeks/IV/liquidity/event context and the same underlying forecast, with historical option-P&L claims still forbidden until an accepted PIT option-history source exists;
5. surface trade-expression mode, economics and abstention/rejection reasons through the browser/control plane.

The Strategy Evidence Register is intentionally unchanged by this package because no new strategy research result or disposition is created.'''
)
