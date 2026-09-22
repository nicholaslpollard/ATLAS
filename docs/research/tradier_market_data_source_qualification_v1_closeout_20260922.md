# Tradier production market-data source qualification V1 closeout — 2026-09-22

## Status

**COMPLETE WITH LIMITATIONS / REST CAPABILITY MEASURED / NO CURRENT-DATA AUTHORITY**

Frozen contract:

`atlas-tradier-production-market-data-source-qualification-v1`

Contract fingerprint:

`3a14be911be351d465ad3a99ab6dc7d47e985fbd17005af0bb6faa9c7613305d`

Target-workstation evidence fingerprint:

`e78e5bfa26039d6895b2b25ebe377d0242f83a2943fe9854f3f1bd1518310a29`

The qualification used the exactly reproduced 2026-08-14 Phase 7 discovery universe:
**12,066** discovery-eligible symbols. The underlying universe snapshot file used by
the diagnostic had SHA-256
`00ec1231008cf3faac7a0c456d73daae3730b0d09f8b4ea7b5b48680925d2afe`.
The accepted Phase 7 universe fingerprint remains
`98e72372e2a4725b2e90b3f6bf797e085f6ed64e2190454892b5ffa42c240124`.

The diagnostic made production, read-only POST quote requests only. It performed zero
broker reads/writes, zero provider writes, zero order creation and created no PAPER,
LIVE, promotion, confluence or provider-policy authority.

## Observed staged evidence

| Requested | Returned | Coverage | Provider latency | Response bytes | Structural status |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 1 | 100.0% | 0.317 s | 525 | PASS |
| 10 | 10 | 100.0% | 0.182 s | 4,884 | PASS |
| 100 | 98 | 98.0% | 0.260 s | 47,333 | PASS |
| 250 | 238 | 95.2% | 0.332 s | 114,413 | PASS |
| 500 | 477 | 95.4% | 0.392 s | 229,224 | PASS |
| 1,000 | 952 | 95.2% | 0.439 s | 457,333 | PASS |

All six requests returned HTTP 200. No stage returned an unexpected symbol or duplicate
symbol row and there was no terminal request/provider error. Returned rate-limit
headers consistently reported an allowed production market-data budget of 120
requests/minute.

The frozen completeness rule requires at least 98% coverage with no unexpected or
duplicate symbols. Therefore only the 1-, 10- and 100-symbol stages are complete
under that rule. The 250-, 500- and 1,000-symbol stages remain structurally successful
requests but below the frozen coverage threshold. The final diagnostic status is
therefore exactly:

`DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS`

## Coverage interpretation

The limitation is **symbol coverage / cross-provider identity**, not evidence of a
request-cardinality or transport failure.

The 1,000-symbol stage omitted 48 requested Phase 7 symbols. Of those 48 literal
Massive/Phase-7 tickers:

- 38 contain the provider-native lowercase `p` preferred/security-class notation;
- 3 are dotted class symbols (`BRK.B`, `HVT.A`, `WSO.B`);
- 7 are otherwise plain literals (`HOOZ`, `IWFL`, `LEG`, `TUGN`, `VBX`,
  `VLLU`, `YBMN`).

That distribution does not authorize a generic ticker rewrite. The previously recorded
current-asset stress evidence independently showed that a blanket dot-to-slash
transform recovered only a small subset of dotted misses. ATLAS therefore retains the
original provider-native symbol and requires evidence-backed cross-provider identity
resolution or fallback rather than broad string substitution.

## Returned field surface

For the 1,000-symbol stage, all 952 returned rows contained non-null bid, ask, bid/ask
timestamps, last trade, trade timestamp, volume, average volume, previous close,
description, exchange, type and 52-week extrema. Session open/high/low/close were
present on 939/952 rows and `root_symbols` on 507/952.

This V1 run occurred after the regular U.S. equity session. Field presence therefore
does not establish current actionable freshness. It also does not resolve the
normalization issue already observed in the supplemental stress work where non-positive
provider timestamps must be treated as absent/UNKNOWN rather than converted to extreme
epoch age.

## Closeout decision

V1 is closed as useful positive REST transport/cardinality evidence with explicit
coverage limitations.

It proves:

- the production token can read Tradier market data;
- the POST quote path handles the frozen staged request sizes through 1,000;
- observed request latency remains sub-second through 1,000 symbols;
- missing requested symbols are returned as partial coverage rather than transport
  failure;
- no unexpected or duplicate symbol rows were observed.

It does **not** prove:

- complete Phase 7 symbol coverage;
- cross-provider symbol identity resolution;
- quote/trade freshness thresholds;
- streaming capacity, reconnect or recovery behavior;
- live-data fallback semantics;
- options-chain economics;
- broker execution quality;
- account/order safety;
- PAPER or LIVE authority.

The selected target architecture remains **Tradier -> Alpaca -> Webull ->
DATA_UNAVAILABLE/abstain** for future current-data routing, but this closeout does not
promote that target into runtime authority by itself.

## Ordered continuation

Do not broaden V1 or rerun it merely to seek a different coverage result.

The next Tradier implementation work should be separately versioned and should focus
on the runtime gaps that actually remain: evidence-backed provider-symbol resolution,
current-state normalization/freshness, per-symbol fallback semantics and bounded
candidate/open-position streaming. Those packages may use the existing supplemental
13,412-symbol stress evidence rather than repeating broad load tests without a new
question.

The current research/data-foundation work may now return to Historical Option
Reference V6. V6 remains fail-closed on the ARTC deliverable/CFI conflict; the already
accepted next evidence step is the read-only ARTC diagnostic. No V7 resolver or
quarantine rule may be created until that evidence is reviewed.
