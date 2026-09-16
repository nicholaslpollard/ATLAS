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
    "## 2026-09-16 — underlying move/time forecast foundation",
    """## 2026-09-16 — underlying move/time forecast foundation

Track A now has a versioned, broker-neutral underlying move/time forecast contract: `93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1`. This object sits **before instrument selection** and carries the distribution evidence needed by the economic actionability layer: signed-return mean/median and p10/p25/p75/p90, probability of a positive underlying return, MFE/MAE, forecast horizon, source/sample lineage, uncertainty, and direction-relative move-threshold timing/path probabilities.

Directional forecasts may carry one or more unique move thresholds such as 1/2/3/5%; larger thresholds cannot report a higher touch probability than smaller thresholds. Favorable-first, adverse-first and same-interval-collision probabilities are validated for internal consistency, and favorable timing must fit inside the forecast horizon. Neutral forecasts intentionally carry no favorable/adverse threshold table. Unavailable forecasts remain first-class objects but may not carry a partial distribution.

The schema enforces PIT ordering (`evidence_cutoff_utc <= forecast_created_utc`), timezone-aware timestamps, finite numerics and a SHA-256 source fingerprint. It is explicitly underlying-only: historical option P&L, instrument-selection authority, broker reads/writes, PAPER, LIVE and strategy-promotion authority are all forbidden. The existing Phase 13 equity-only case-file contract and Phase 15 equity execution path are unchanged; later simulator integration will use a separately versioned product path rather than mutating those accepted contracts.""",
)

append_once(
    "docs/roadmap.md",
    "## 27. Underlying move/time forecast foundation — 2026-09-16",
    """## 27. Underlying move/time forecast foundation — 2026-09-16

### 27.1 Contract boundary

The broker-neutral product forecast contract is `93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1` (`atlas-underlying-move-time-forecast-v1`). It converts supported strategy/model/empirical evidence into a common underlying-price-path distribution **before** stock or option construction.

An available forecast carries:

- identity, direction, forecast creation time and PIT evidence cutoff;
- horizon in minutes or sessions;
- method/source labels, SHA-256 source lineage and sample size;
- reference price;
- mean, median, p10, p25, p75 and p90 signed underlying return;
- probability of a positive underlying return;
- direction-normalized mean MFE and MAE;
- optional uncertainty score;
- for directional forecasts, unique direction-relative move thresholds with favorable/adverse touch probabilities, favorable-first/adverse-first/same-interval ordering probabilities and median favorable time.

The schema sorts thresholds deterministically and rejects probability curves that become larger at a more difficult move threshold. It also rejects unordered quantiles, non-finite values, future evidence, timing beyond the horizon and internally inconsistent path-order probabilities. A neutral available forecast carries a return distribution but no directional threshold table. An unavailable forecast carries identity/method/source/reasons only and cannot smuggle partial numeric evidence downstream.

### 27.2 Authority and compatibility

The forecast is underlying-only and cannot claim historical option P&L or grant instrument-selection, broker, PAPER, LIVE or promotion authority. It does not modify `Phase13CaseFile`, whose v1 primary instrument remains equity, and does not modify the Phase 15 order builder. This preserves the accepted execution path while Track A builds a separately versioned simulator/control-plane path.

### 27.3 Next implementation sequence

1. add a deterministic adapter that turns an available move/time forecast plus explicit stock economics into a stock `EconomicCandidate` for the universal actionability gate;
2. define an option-scenario input/output interface using the same underlying distribution, with executable quote/spread, Greeks, IV scenario, theta, liquidity and event completeness required before an option `EconomicCandidate` can exist;
3. create a versioned simulator decision case joining forecast + actionability policy + trade-expression decision + broker-neutral portfolio sizing, with abstention as a normal outcome;
4. expose those read-only decision objects and reason codes through the browser/control-plane surface;
5. leave live/paper order creation on the existing authority-gated path until a later explicitly accepted integration package.

The immediate goal is a usable account simulator driven by deterministic, inspectable evidence even while no strategy is historically promoted.""",
)
