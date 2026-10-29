# V41 — American Leisen–Reimer option IV + fixed SPY 20-return variance decision

## Why this matters after V37 and V40

The accepted European-equivalent option-Greeks module is not the same as the frozen SPY pilot's intended **American-style** IV and early exercise model. The pilot explicitly requires a 101-step Leisen–Reimer binomial model for each call and put, historically sourced SOFR and dividend inputs, and a signed comparison of 20 strictly prior economic log-return variance to the same-maturity pair implied variance.

V41 introduces a **pure pricing/decision engine** in `packages/simulation/american_option_iv_lr_v41.py`:

- Implement Peizer–Pratt inversion of the terminal binomial probability for a fixed odd **101-step Leisen–Reimer** tree; use backward induction and max(continuation, early exercise).
- Independently invert observed, valid, two-sided call and put *midpoints* by bounded bisection of the American tree. Model premiums never overwrite archived bid/ask prices or fabricate fills.
- Demand historically qualified original quote source, standard contract deliverable, risk-free rate and **dividend-equivalent yield**. Missing input or unknown source availability blocks IV instead of silently setting SOFR/dividend to current values/zero.
- Accept 20 strictly prior completed economic log returns with elapsed real calendar seconds; calculate variance rate `sum(r_i^2) / sum(delta_seconds_i)` and forecast to the actual option model maturity. Compare against average `(call_IV^2 + put_IV^2)/2 * maturity_seconds/(365*86400)`. Enter long straddle only if *forecast variance exceeds implied pair variance*, otherwise abstain.
- Explicit `BLOCKED` for historical PIT corporate-action/rate/dividend/quote inputs not qualified. A calculated model IV by itself is not verified executable order pricing or account P&L.

**Validation:** 101-step Leisen–Reimer American non-dividend call reprices the Black–Scholes analytic European call closely, American put has an early-exercise premium, and IV inversion recovers known tree volatility. Unit tests also cover bad quote and even-step inputs, blocked historical sources, and the positive/negative 20-return variance screen.

## Important limits before true historical pilot signal

An American early exercise tree with a single *continuous dividend-yield equivalent* is NOT a complete SPY discrete-ex-date exercise model. Exact historical cash distributions and their publication times, rate term structure, model maturity and the original OCC deliverable still need independent source qualification. V41 marks `discrete_dividend_ex_date_model_qualified = False` and does not grant historical strategy eligibility on its own. True source availability at the frozen 10:00 decision/10:01 order clock, plus exit and actual order liquidity, still determine whether the simulator can produce qualified historical account performance.

V40's dynamic source acquisition provides exact 10:01 historical options and decision-day OI publication candidates. V41 makes the next integration stage concrete: parse those archived sources and qualified historical PIT corporate actions and rates, compute American call+put IV, apply the frozen signal, and ask V39 for additional newly eligible/exit sources when needed. No fixed candidate roster or provider-call prohibition should be added.

V41 itself is a library, not a direct trade simulator or a price-acquisition job.
