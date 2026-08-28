# Future News-Sentiment and Option Fair-Value Requirements

**Status:** downstream design requirement for Phase31 and later. This document **does not alter the frozen Phase30 scientific policy**, its fingerprint, its four hypotheses, its authorized metadata-only news fields, or its protected-read boundary.

Phase30 remains restricted to `id`, `published_utc`, and exact provider-native `tickers`. Historical article text and provider-generated sentiment/insights remain provenance only unless their point-in-time revision/model-vintage semantics are separately proven. The requirements below define how ATLAS should use richer news and option valuation later without retrofitting them into Phase30.

## 1. News Sentiment Evidence and Re-evaluation Layer

The default operating mode should be **Supporting Evidence**. Sentiment does not create trade authority and should not mechanically override a supported alpha thesis, but material contradictory information must be capable of reducing expected value, forcing re-evaluation, or suppressing a new entry.

The layer must evaluate at least:

- ticker/entity relevance and ambiguity;
- source quality and credibility;
- event category and severity;
- positive/negative/neutral direction;
- sentiment/model confidence;
- freshness and deterministic time decay;
- novelty versus duplicate/syndicated coverage;
- agreement or conflict with the proposed trade direction;
- whether the information arrived before entry or after a position already exists.

Required behavior:

1. **No relevant news:** no score adjustment.
2. **Neutral, weak, stale, or low-confidence news:** little or no adjustment.
3. **Strong aligned news:** bounded confidence/expected-value support; positive evidence cannot create a trade by itself.
4. **Moderate contradictory news:** haircut expected profitability/confidence, rerank the candidate, and allow tighter portfolio admission or smaller sizing if the accepted risk policy supports it.
5. **Strong contradictory news:** mandatory thesis re-evaluation before a new entry. Recompute expected profitability/risk with the new evidence; the result may remain a trade, become lower conviction, or become PASS/no-trade.
6. **Severe event risk:** bankruptcy/liquidity distress, material fraud/accounting allegations, major regulatory action, trading halt, merger/acquisition terms, earnings/guidance shock, major litigation/product-safety/cyber events, or another event class proven capable of invalidating ordinary assumptions must enter a dedicated event-risk gate. These are not treated as a small linear score penalty.
7. **Post-entry material news:** trigger position/risk re-evaluation under the accepted exit/risk policy. It must not rewrite the original signal or historical record.

Syndicated/duplicate articles must be clustered so repeated copies do not multiply conviction. Positive support should be capped; credible contradictory downside evidence may carry a larger penalty because ignoring thesis-invalidating information is more dangerous than missing a small incremental positive catalyst.

Weights, thresholds, event classes, and time-decay constants must be frozen from point-in-time-safe or prospectively captured evidence before they gain authority. Retrospective provider sentiment may not be assumed PIT-safe merely because an old article is returned by a current API.

Planned operator modes:

- `Off`
- `Supporting Evidence` — default
- `Required Confirmation` — optional stricter policy only after separately validated

## 2. Option Fair-Value Engine

Phase31 must make option valuation an explicit contract-selection capability rather than an implicit generic score. Directional alpha answers whether ATLAS wants LONG/SHORT exposure; the **Option Fair-Value Engine** helps choose the best eligible contract or defined-risk structure for that thesis.

Black-Scholes-Merton (BSM) should be a standardized reference model, but not the sole valuation authority. ATLAS must avoid circular logic: taking an option's market-implied volatility, feeding that same IV into BSM, and calling the resulting market-consistent price an independent estimate of under/overvaluation does not create an independent fair-value edge.

The engine should use an independently estimated fair volatility/value framework incorporating, where available and validated:

- fitted implied-volatility surface;
- neighboring strikes and expirations;
- skew and term structure;
- realized and forecast volatility;
- known event volatility;
- risk-free rate;
- dividends and ex-dividend timing;
- underlying price and strike;
- exact DTE/time to expiry;
- executable bid/ask rather than an untradeable midpoint assumption;
- liquidity, spread, volume, and open interest;
- Greeks and sensitivity to volatility/time/underlying assumptions.

For American-style equity options where dividends or early exercise matter, use a validated American-option model such as an appropriate binomial/lattice method rather than forcing classic European BSM assumptions.

The engine should produce a fair-value **range with uncertainty**, not false precision, and preserve audit fields including model used, volatility source, assumptions, executable price, estimated valuation edge, sensitivities/Greeks, dividend/early-exercise flags, data freshness, and confidence.

Model cheapness never overrides liquidity/spread or risk eligibility. For long-premium directional expression:

- LONG thesis -> prefer fairly or underpriced eligible CALL exposure;
- SHORT thesis -> prefer fairly or underpriced eligible PUT exposure.

Overpriced options may be rejected or down-ranked even when directionally aligned. Any future option-selling strategy requires separate strategy/risk authorization; an overpriced contract alone is not permission to sell naked or otherwise add short-option risk.

Planned operator modes:

- `Off`
- `Rank Boost` — default
- `Require Positive Valuation Edge`

## 3. Phase Placement and Validation

- **Phase30:** unchanged metadata-only event-arrival alpha research.
- **Phase31:** implement deterministic news-evidence/re-evaluation contracts and the Option Fair-Value Engine as part of signal-to-trade/instrument selection, using accepted Phase12/13/14 components where applicable.
- **Phase32:** historical replay/stress must measure the incremental effect and failure modes of these enabled decision layers where PIT-safe evidence exists.
- **Phase33:** prospectively validate news sentiment/vintage capture, option valuation inputs, contract rankings, and real PAPER execution consequences.
- **Phase34:** measure realized calibration, option-selection quality, news-event outcomes, drift, and degradation; no silent self-reweighting.

Neither layer creates alpha, PAPER, or LIVE authority by itself. Both remain subordinate to the accepted ATLAS authority, risk, chronology, provenance, and no-workaround rules.
