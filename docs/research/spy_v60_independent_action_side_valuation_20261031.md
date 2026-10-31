# V60 — Acted-side quote valuation rather than whole-quote rejection

## Direction, contract and side

The objective is to avoid rejecting a buy ask when only the bid is anomalously low, or a sell bid when only the ask is anomalously high. The same logic applies independently to calls and puts. Mispricing the *opposite* option right is not proof that the intended option is mispriced.

The existing historical_option_greeks_v1.py already provides Black–Scholes–Merton European-equivalent theoretical pricing. It is a model benchmark for American-style SPY ETF options and is never an executable market quote or a guaranteed fill.

The new spy_v60_independent_action_side_valuation.py applies:

- Buy CALL or PUT: evaluate the ASK against independent fair-price interval. Reject overpriced asks even if bid is close; allow a research candidate when ask is fair but bid is abnormally low.
- Sell CALL or PUT: evaluate the BID against independent fair-price interval. Reject underpriced bids even if ask is close; allow a research candidate when bid is fair but ask is abnormally high.
- If acted price is implausibly *better* than model fair value, abstain pending independent corroboration instead of assuming free arbitrage.
- If both quote sides are compatible with a very wide model band, or the model cannot attribute the wide spread to the opposite side, abstain rather than approve it.
- Require sufficient size on the acted side, original bid/ask numeric and noncrossed, and freshness of original quote and independent underlying spot. Do not override the existing 1s/3s action latency, adverse ask drift, commissions, portfolio cash, stop and full-quote provenance.
- Use independent prior volatility bounds (not the suspect quote midpoint), contemporaneous spot, historical rates and dividends with strict as-of clocks and source IDs. A quote may be marked model-compatible in this developmental test without asserting a broker fill.
- The experimental BSM band is volatility-range model price plus $0.02 option premium tolerance; if the independent volatility band implies over 15% fair-price uncertainty, abstain.

## June 13 actual evidence

V59 verified June 13 SPY 598 PUT at 10:00:01: BID $1.05 x2, ASK $1.60 x5, with spread 41.5% of midpoint. At 10:00:00 BID was $1.70 x3 and ASK $1.81 x10. Bid fell 38.2% in one second while ask fell 11.6%. The 10:00:02 quote (bid $1.39 / ask $1.60) is future information at 10:00:01 and cannot be used to authorize a trade at 10:00:01. V59 found five spread-invalid quotes among 19,860 original second-level quotes and no timestamp gaps. The user wants *sell bid* quality evaluated independently of a potentially high ASK.

June 11 602 PUT was NO_ENTRY because the actual action ASK moved beyond the permitted adverse change threshold. BSM quote-side quality cannot invalidate the distinct latency/action-price drift protection.

The uploaded V59 report does **not** include a verified independent SPY tick spot or prior-only volatility band at the exact 10:00:01 decision. Therefore V60 currently cannot certify the $1.05 bid as fairly priced or unreasonably low, and cannot convert that historical exit to a fill. Never use current suspect BID/ASK midpoint to derive IV and then validate that same quote with it.

## Required actual-data workflow

1. Read prior archived SHA-verified original SPY spot at exact decision-time second, or acquire it using the supported historical provider flow and retain immutable original receipt, with evidence of temporal availability.
2. Calibrate implied-volatility band from *separate prior qualifying option observations* and contemporaneous prior spot (ideally nearby strikes/rights), with rate/dividend/expiry provenance. Do not use the wide-spread target quote itself.
3. Reprice both call and put theoretical intervals at the action timestamp, then assess action-specific bid versus ask, quote conditions, size, timing, spread-side attribution, and limit-order feasibility. Preserve a separate no-reference/uncertain state.
4. Compare candidate policy across new chronological dates with immutable per-trade records, original and model prices, rejected versus salvaged decisions, fees, spread, time-to-expiry, modeled quote fills, and independent cash path. The reviewed June 13 case is **in-sample**.
5. Preserve original V55/V56 and V57/V58/V59 reports. An isolated invalid-quote skip experiment in run_spy_v60_quote_hygiene_recovery.py is a separate non-promoted alternate; it must not treat an untrusted sell bid that could cross a risk stop as proof of an executable stop.

## Source background

Options Industry Council explains bid/ask and displayed size in https://prd-web.optionseducation.org/news/understanding-the-bid-and-ask-prices-for-options . OCC's mark-to-market method smooths noisy quotes and explicitly distinguishes theoretical marks from tradable values: https://prd-web.optionseducation.org/news/mark-to-market-where-every-option-finds-its-true-value .
