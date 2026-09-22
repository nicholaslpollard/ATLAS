# Tradier current-asset REST stress diagnostic — 2026-09-22

## Purpose

This document records a supplemental target-workstation Tradier REST stress diagnostic
performed while the frozen
`atlas-tradier-production-market-data-source-qualification-v1` prerequisite was being
recovered.

It does **not** replace or amend the frozen V1 qualification contract. V1 remains bound
to the accepted Phase 7 discovery-eligible universe and must still be rerun only after
the exact 2026-08-14 reference snapshot and Phase 7 universe have been reproduced.

The diagnostic had no provider-policy, strategy, promotion, PAPER or LIVE authority.

## Source population

The surviving Alpaca SIP V2 source snapshot was used only to provide a current,
deterministic stress population without resurrecting retired V1 artifacts.

Observed source:

- V2 run id:
  `4bec39617f81727aa7e351f0f9e11a21110ff0e3244819e9476d45174f0bb139`
- asset snapshot:
  `data/v2_build/alpaca_sip_v2/canonical/identity/assets_snapshot.parquet`
- asset snapshot SHA-256:
  `43a5645d4366e7f7294e14f60596c5e753db6158c394a62262fdd283bbab151a`
- active + tradable + `us_equity` symbols: **13,412**
- deterministic sample size: **1,000**
- sample SHA-256:
  `fbc43ffbb3b046161615614d3362987137c2ffea9bef9af0389ced32134ceba4`
- retained anchors: SPY, QQQ, AAPL, MSFT, NVDA

The 1,000-symbol list was built by retaining the liquid anchors when present and then
stable SHA-256 ordering the remaining active/tradable V2 symbols. The existing V1 CLI
was invoked with those symbols explicitly, so the run correctly identified the source
as `EXPLICIT_SYMBOLS`.

## Observed Tradier result

The production POST quote endpoint completed every requested stage without a terminal
provider/request failure.

Evidence fingerprint:

`3928c7dcbff886a098cb3ffa6231e8595acbe5a6cb91106709ca5b7541474d7b`

| Requested | Returned | Coverage | Provider latency | Response bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 100.0% | 0.305 s | 520 |
| 10 | 10 | 100.0% | 0.173 s | 4,858 |
| 100 | 96 | 96.0% | 0.304 s | 46,381 |
| 250 | 241 | 96.4% | 0.347 s | 115,844 |
| 500 | 482 | 96.4% | 0.391 s | 231,382 |
| 1,000 | 962 | 96.2% | 0.544 s | 461,708 |

The 1,000-symbol POST therefore established that the observed production endpoint can
accept and return a large response at that request size on the target workstation.
No practical POST cardinality ceiling was encountered through 1,000 requested symbols.

The 1,000-symbol stage returned 38 missing source symbols:

`AGM.PRH, AUB.PRA, BHR.PRB, BRK.B, CAPNR, CFR.PRB, CHPGR, CMRE.PRD, CRACR,
FLG.PRU, GFR.RT, GNL.PRD, HVT.A, ICR.PRA, IEAGR, LKSPR, MCAHR, MET.PRE,
MS.PRK, NGL.PRC, OPP.PRB, PBI.PRB, PEB.PRF, PEB.PRH, PLUN.RT, PNFP.PRB,
PSA.PRL, PSA.PRQ, RAC.U, RF.PRC, SCE.PRN, SNUS.PRI, SZZLR, TAVIR, TRTN.PRB,
TWO.PRC, WRB.PRF, WSO.B`.

The missing population is strongly concentrated in provider-specific symbol forms:
30/38 contain a dot. Of those, 24 match the literal `.PR*` pattern, two end in
`.RT`, one ends in `.U`, and three are other dotted forms. Eight missing symbols
are plain undotted literals.

Tradier's current Market Data documentation explicitly states that warrants,
preferred classes and other specialized securities use `/` where some other brokers
use `.`, including the example `BRK.B -> BRK/B`. That provider documentation makes
dot-to-slash normalization a concrete follow-up hypothesis for the dotted misses, but
ATLAS has **not** accepted that transformation merely from documentation or from this
sample. It must be tested read-only, preserve the original provider-native symbol and
become a separately versioned mapping rule before any operating use.

Documentation reference:

- `https://docs.tradier.com/docs/market-data`

## Follow-up symbol probe

A read-only follow-up tested the documented dot-to-slash hypothesis directly.

Dotted-symbol probe:

- requested: **30**
- returned: **4**
- coverage: **13.333%**
- provider latency: **0.265 s**
- evidence fingerprint:
  `ba559a59019b4b25d0d099e416efeada7679e26c573df8bc65bbc4e884424ff6`

Because the missing list omitted only four transformed literals, the successful
translations were `BRK/B`, `HVT/A`, `RAC/U` and `WSO/B`. The remaining 26
slash-transformed literals were still absent. This demonstrates that a mechanical
`.` -> `/` rule is valid for only a subset of the observed cases and may not be
generalized across preferreds, rights, warrants or other specialized symbols.

Plain-symbol probe:

- requested: **8**
- returned: **0**
- coverage: **0.0%**
- provider latency: **0.190 s**
- evidence fingerprint:
  `39032d1f7c0af09c0bcb993025cd0ca768c563606bf9fa0424aa2d6b1c62cd53`

The eight unchanged plain literals were `CAPNR, CHPGR, CRACR, IEAGR, LKSPR, MCAHR,
SZZLR, TAVIR`. Their absence cannot be attributed to dot/slash notation.

The appropriate next step is therefore not a broad punctuation rewrite. Any accepted
cross-provider mapping must be evidence-backed per security/symbol class, preserve the
original provider-native identifiers and fail closed when no deterministic mapping is
proven.

Returned `X-Ratelimit-*` headers were retained as raw evidence. The observed
`used` value was not monotonic across sequential requests, so no cumulative-rate
semantics are inferred from that field in this diagnostic.

## Interpretation

This run establishes useful engineering evidence:

1. production Tradier authentication and POST quote transport are working;
2. 1,000-symbol POST requests are operational on the observed entitlement/workstation;
3. latency remained below 0.6 seconds through the 1,000-symbol stage;
4. broad coverage on this deterministic current-asset sample was 96.2%;
5. the principal observed limitation is symbol coverage/representation, not request
   cardinality or transport failure.

It does **not** establish:

- formal V1 qualification acceptance;
- full 13,412-symbol current-universe coverage;
- an accepted symbol-normalization map;
- quote timestamp/freshness equivalence against Alpaca/Webull;
- streaming capacity, recovery or freshness;
- option-chain coverage/economics;
- broker/account/order safety;
- any current-provider-policy change;
- PAPER or LIVE authority.

## Ordered continuation

The accepted repository sequence remains unchanged:

1. reacquire the exact 2026-08-14 Massive Phase 4 reference snapshot using the
   rate-aware adapter accepted in PR #201;
2. repair/reproduce the accepted reference identity state as required by the existing
   Phase 4/7 contracts;
3. rebuild Phase 7;
4. require exactly **12,066** discovery-eligible instruments and universe fingerprint
   `98e72372e2a4725b2e90b3f6bf797e085f6ed64e2190454892b5ffa42c240124`;
5. rerun the frozen Tradier REST V1 qualification against that population;
6. only after formal REST evidence is accepted, separately qualify cross-provider
   symbol normalization, quote freshness/feed quality and bounded streaming behavior.

This source/transport diagnostic does not belong in the Strategy Evidence Register
because it changes no strategy evidence or research disposition.


## Full-universe live quote ingestion benchmark

With the regular session still open on 2026-09-22, a supplemental read-only benchmark
measured end-to-end REST quote ingestion for the complete surviving Alpaca SIP V2
current asset population: **13,412 active, tradable US equities**.

The same exact symbol population was requested using four batching strategies:

| Batch size | Requests | Returned unique | Coverage | Total wall time | Provider latency |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 14 | 12,775 | 95.251% | 7.202 s | avg 0.495 s / max 0.707 s |
| 2,000 | 7 | 12,775 | 95.251% | 4.470 s | avg 0.633 s / max 0.749 s |
| 5,000 | 3 | 12,775 | 95.251% | 2.865 s | avg 0.941 s / max 0.979 s |
| 13,412 | 1 | 12,775 | 95.251% | **2.009 s** | **1.983 s** |

Every strategy returned the exact same **12,775** unique symbols and therefore the
same **637** missing symbols. This strongly rules out request-size truncation as the
cause of the observed coverage gap through the tested 13,412-symbol request.

The single-request full-universe result transferred approximately **5.853 MiB** and
processed:

- 13,412 requested symbols in 2.009 seconds;
- 6,676 requested symbols/second;
- 12,775 returned symbols in the same request;
- 6,359 returned symbols/second.

The observed endpoint therefore accepted the complete 13,412-symbol current-asset
population in one POST on the target workstation. No POST cardinality ceiling was
observed at that scale.

### Architectural implication

This result materially supports a two-tier current-market-data design:

1. broad discovery remains driven by the local analytical lake and deterministic
   research/discovery state;
2. a **single bounded Tradier REST snapshot** can refresh current prices for the broad
   current universe in roughly two seconds under the observed production entitlement;
3. the system can then narrow/rank candidates locally; and
4. streaming can remain reserved for finalists, pending orders and open positions
   where sub-second updates matter economically.

This is more efficient than treating full-universe streaming as the primary discovery
transport, and it preserves stream capacity for high-value symbols.

The benchmark does **not** establish a safe polling cadence. Provider limits,
acceptable load, freshness requirements and retry/recovery behavior must be frozen
separately before recurrent broad-universe polling is accepted. It also does not
change the 95.251% raw symbol-coverage limitation or accept any normalization rule.

The formal Tradier V1 Phase 7 qualification remains a separate frozen gate.


## Raw quote field-semantics inspection

A 10-symbol production sample was captured during the regular session at approximately
19:56:46 UTC using SPY, QQQ, AAPL, MSFT, NVDA, AMD, TSLA, IWM, BRK/B and HVT/A.
All ten requests were returned in one POST (HTTP 200) in 0.240 seconds / 4,935 bytes.

Across the ten returned rows, the following fields were non-null for all ten:
`ask, ask_date, askexch, asksize, average_volume, bid, bid_date, bidexch, bidsize,
change, change_percentage, description, exch, last, last_volume, prevclose, symbol,
trade_date, type, volume, week_52_high, week_52_low`.

`open, high, low` and `root_symbols` were present for 9/10. `close` was null for
10/10 during the regular session.

Nine liquid symbols showed current-session quote/trade timestamps around
19:56:44 UTC. HVT/A exposed the required fail-closed counterexample:

- last trade timestamp: 2026-09-21 23:00:00.001 UTC;
- bid timestamp: 2026-09-22 19:56:09 UTC;
- ask timestamp: 2026-09-22 19:50:01 UTC;
- bid/ask: 28.53 / 30.94;
- session volume: 35;
- open/high/low: null.

Therefore row presence alone is not sufficient current-data evidence. A normalized
Tradier snapshot must independently preserve and gate trade, bid and ask freshness,
spread/quote geometry and liquidity. Illiquid/stale rows must remain observable but
must not be promoted to actionable current state.

Additional semantic observations:

- `prevclose` was populated 10/10 while intraday `close` was null 10/10, so
  prior-session comparison must not depend on `close` during the regular session.
- returned 52-week extrema are not necessarily updated with current-session extremes:
  both AAPL and AMD had current-session highs above the returned `week_52_high`.
  ATLAS may retain the provider field as descriptive context, but must not use it as
  an unreconciled real-time breakout boundary.
- `root_symbols` is provider metadata rather than a canonical ATLAS identity key;
  e.g. AMD returned `AMD,AMD1`, TSLA returned `TSLA,TSLA1`, BRK/B returned
  `BRKB`, while HVT/A had no root-symbol value.

The raw diagnostic was intentionally persisted only beneath ignored local research
state. A production current-state adapter should persist an explicit normalized schema
and provenance/freshness metadata rather than archive unrestricted provider payloads.


## Pre-close full-universe raw capture

A final production read-only snapshot was captured while the 2026-09-22 regular session
was still open.

Observed capture:

- request started: `2026-09-22T19:58:42.512356+00:00`
- capture completed: `2026-09-22T19:58:44.567733+00:00`
- requested symbols: **13,412**
- returned rows: **12,775**
- coverage: **95.251%**
- provider latency: **2.038 s**
- total wall time: **2.055 s**
- response bytes: **6,139,901**
- local ignored artifact:
  `data/research/provider_qualification/tradier/full_universe_raw/20260922T195844Z.json`

This independently reproduced the earlier full-universe benchmark immediately before
the regular-session close. The returned cardinality remained exactly 12,775 and the
wall time remained approximately two seconds.

The raw artifact is local research evidence only and is intentionally not committed.
Any post-close normalization/freshness analysis must use the stored capture timestamp
and provider timestamps from this immutable snapshot rather than analysis wall-clock
time, so closing-bell delay does not contaminate the measured freshness distribution.


## Full-universe normalized snapshot quality

Post-close analysis of the immutable 19:58:44 UTC raw capture produced a normalized
12,775-row Parquet snapshot (approximately 1.103 MiB).

Observed raw-population quality metrics:

- valid bid/ask geometry: **12,764 / 12,775 (99.91%)**
- quote freshness <= 5 s: **1,763 (13.80%)**
- quote freshness <= 15 s: **5,728 (44.84%)**
- quote freshness <= 30 s: **7,068 (55.33%)**
- trade freshness <= 5 s: **2,027 (15.87%)**
- trade freshness <= 30 s: **5,588 (43.74%)**
- trade freshness <= 60 s: **6,298 (49.30%)**
- session open/high/low populated: **11,616 (90.93%)**
- previous close populated: **12,762 (99.90%)**
- session and average volume populated: **12,775 (100%)**
- median quote age: **19.567 s**
- median trade age: **65.738 s**
- median spread: **18.594 bps**

The broad raw population contains many thin, stale and specialized securities. Examples
among the stalest/widest rows included warrants, units, preferred-like literals and
very low-volume securities. Therefore these percentages describe the complete
Alpaca-active/tradable source population, not the narrower accepted Phase 7
discovery-eligible population and not an execution-ready candidate set.

A diagnostic normalization defect was also exposed: provider timestamp value `0` was
converted to an epoch-based age of roughly 1.79 billion seconds rather than being
classified as missing/unknown. Those extreme maximum-age values must not be interpreted
as genuine quote staleness. Production normalization must treat non-positive provider
timestamps as absent and retain an explicit freshness-unknown state.

The quality result reinforces a layered design:

1. row presence != current/actionable data;
2. current state must preserve independent trade/bid/ask timestamps and freshness;
3. broad discovery should apply security-type, liquidity, spread and freshness gates
   before a row becomes current actionable evidence;
4. stale/illiquid rows remain observable but fail closed;
5. the same quality analysis must later be repeated on the exact reproduced Phase 7
   discovery population before any formal coverage/freshness claim is accepted.

The observed 2-second acquisition speed remains valid. This quality analysis narrows
what that speed means: Tradier can rapidly return a broad current-market snapshot, but
ATLAS must locally distinguish fresh/liquid/actionable rows from stale or thin
provider rows before discovery or execution use.


## Near-close discovery-quality sensitivity

The full-universe quality snapshot was captured at 15:58:44 America/New_York, less
than two minutes before the regular-session close. It is therefore a useful
near-close regime observation, not a whole-day representativeness claim.

Diagnostic sensitivity across the 12,775 returned rows showed:

- quote age <=30 s and spread <=100 bps: **6,771 (53.00%)**
- the same gate with average volume >=50,000: **4,588 (35.91%)**
- average volume >=100,000: **4,179 (32.71%)**
- average volume >=500,000: **2,669 (20.89%)**
- average volume >=1,000,000: **1,875 (14.68%)**

The quality relationship with liquidity was strong. Under the <=30 s / <=100 bps
diagnostic gate, **90.54%** of symbols averaging at least 1M shares/day were usable,
**85.84%** of the 500K-1M bucket were usable, and **67.90%** of the 100K-500K bucket
were usable. The raw broad universe's weak freshness statistics are therefore
materially concentrated outside the most liquid population.

No threshold above is accepted production policy. These are sensitivity observations
only and should be repeated at multiple regular-session regimes (open, mid-morning,
midday, power hour/near-close) before any freshness or liquidity gate is frozen.

## Candidate multi-pass rediscovery design

The observed ~2-second full-universe REST snapshot makes a bounded multi-pass discovery
cycle technically plausible without broad streaming.

A future versioned design should:

1. perform one broad current snapshot;
2. immediately classify each requested symbol as fresh/usable, returned-but-unresolved,
   or missing;
3. run discovery immediately on fresh/usable rows rather than waiting for every symbol;
4. re-request only the unresolved/missing cohort after a bounded interval;
5. merge a retry only when its provider timestamps/quality improve the stored state;
6. incrementally admit newly usable symbols into rediscovery;
7. preserve symbols that remain stale/missing as explicit unavailable evidence rather
   than fabricating or carrying forward currentness;
8. stop after a frozen retry budget/horizon.

This would allow a stock whose first-pass quote was stale, incomplete or absent to
become discovery-eligible on a later pass without recomputing or delaying the already
usable majority. Retry cadence, maximum attempts, liquidity prioritization and
incremental-discovery semantics remain future contracts and are not authorized by this
diagnostic evidence.
