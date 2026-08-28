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

## 4. Alpaca/Benzinga News as a Future Independent Source

Alpaca's current Market Data documentation exposes historical news at `https://data.alpaca.markets/v1beta1/news`, states that the history dates back to **2015**, identifies **Benzinga** as the current source, and explicitly lists sentiment-model training and real-time news trading as supported use cases. Alpaca also exposes a real-time news WebSocket. The news schema includes article identity, symbols, headline/summary/content, `created_at`, and `updated_at` timestamps.

This is a useful future ATLAS source for three distinct reasons:

1. **Longer research corpus:** the 2015 start extends well before the current Massive Phase30 research interval and could support future language/event-model research if point-in-time safety is established.
2. **Cross-provider evidence:** Alpaca/Benzinga can be compared with Massive coverage for missing articles, ticker linkage, timestamp disagreement, duplicate/syndicated stories, and source-specific bias rather than silently replacing one provider with the other.
3. **Prospective vintage capture:** the real-time WebSocket can be archived exactly as received, including later updates, giving ATLAS a genuinely point-in-time text corpus for future sentiment/event models.

### Entitlement must be proved, not assumed

As of the 2026-08-28 documentation review, Alpaca's Trading API market-data page lists the default **Basic** plan as free with **200 historical API calls/minute**, while Algo Trader Plus is listed at 10,000 calls/minute. The current historical-news page and endpoint reference do not publish a separate Basic-versus-paid news entitlement matrix. Historical news therefore remains **candidate available** rather than accepted available until an authenticated read-only request succeeds with the actual ATLAS Alpaca credentials and its returned rate-limit/entitlement behavior is recorded.

A future feasibility probe must be read-only and record HTTP status, request/rate-limit headers where available, earliest retrievable article time, pagination behavior, content availability, and whether both paper and live Trading API credentials have equivalent market-data entitlement. A `401`, `403`, or plan restriction is a legitimate feasibility result; ATLAS must not silently upgrade plans or substitute a different source to manufacture PASS.

### Point-in-time warning

`created_at` and `updated_at` are valuable provenance, but they do **not by themselves prove that a historical REST response contains the exact text version visible at the original publication time**. Historical REST text may reflect a later article revision. Therefore:

- retrospective Alpaca headline/content must not be granted historical alpha authority until revision/vintage semantics are demonstrated;
- an `updated_at` timestamp after the trading decision time is a warning, not proof that the returned content can be safely rolled back;
- historical Alpaca text may be useful for non-authoritative corpus exploration/model pretraining, but not for a leakage-sensitive backtest merely because the article date is old;
- the strongest path for future sentiment authority is prospective WebSocket capture with immutable versioning from first receipt forward.

This Alpaca/Benzinga requirement does not alter Phase30, does not rescue or retune its negative result, and does not unlock Phase31 without accepted supported alpha.
