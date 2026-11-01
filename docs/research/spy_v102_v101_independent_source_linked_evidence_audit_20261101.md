# ATLAS V102 — Independent V101 source-linked evidence audit and chronological selection probe

Date: 2026-11-01. Research documentation only; no new broker or provider request, no change to V99–V101 strategies, source cache, or protected 2026-05 through 2026-08 holdout. Base is V101 pinned `10ccbdfea1f69ec610152e81147c815efb0bae1d`.

## Workstation result and original uploaded evidence

The user's complete V101 workstation replay passed **67 tests**, and **168 early synthetic V90 scope/execution preflights**. All 18 historical cohort/filter runs completed, emitting **21,600** signed V90-account scenarios. Provider requests=0, broker orders=0. The original V99/V100 source audit reported 630 previously signed source journals and 10,800 prior original accounts verified.

- Full ZIP: `spy_v101_original_news_gate_quote_replay_20261101_171219_full_source_linked_evidence.zip`, byte SHA-256 `0259900980874a1a124233f5d3a97467a0471ae8a739e889b94183b25a166873`.
- Summary ZIP: `spy_v101_original_news_gate_quote_replay_20261101_171219_summary_evidence.zip`, byte SHA-256 `2a82105d95f30d047124b92bf7cad8290e94215076500a99db39ce19b2225677`.
- Signed V101 root fingerprint `e5b0b5e199b05e12605438f44da05e9b95a3b3f5ac095bee8babf9a82569ee39`, crossperiod comparison fingerprint `d24c9b067d5ada40df99c8b81407b26073bd2bc09e3341068bb2a7a033c896bf`.

Independent reviewer inspected both supplied ZIPs: archive CRC passed, 3 common summary members matched full ZIP byte-for-byte; manifest's 20 files matched recorded byte counts, compressed-file SHA and signed document fingerprints; all 18 1,200-scenario groups and **all 21,600 nested V90 accounts** were independently SHA-verified and checked for original scope/execution identity, cash debits/credits, stressed weekly/monthly closed P&L, unfinished option premiums, censorship, no broker orders, and parent association in all 3,600 six-cohort scenario-comparison rows. All 1,335 source-backed news opportunity records retained original source SHA references, with event dates before May 2026. **194,966 individual automated assertions passed; no discrepancy identified.** Raw original ThetaData bytes and original V99 gzip trial payloads were not in these uploaded V101 ZIPs and have not been byte-verified by this particular independent audit. The original news's `max(created_at,updated_at)` is a conservative PIT metadata proxy, not independently verified first publication.

## Results, not a profitability proof

- Account results with known final quote cash: **21,356**. Censored: **244**, including **28 nested accounts** retaining an unresolved option exposure. Censored != zero cash profit.
- Fully comparable six-cohort strategies: **3,356** of 3,600 filter/strategy/execution configurations; **0** positive in all six research cohorts.
- 24h active `NEWS_24H_AT_LEAST_1`: 1,114 complete configurations, 211 positive nominal cumulative six-cohort totals, **0** positive in all six.
- 7-day `NEWS_7D_AT_LEAST_3`: 1,114 complete, 251 positive nominal cumulative totals, **0** positive in all six.
- 24h quiet `NEWS_24H_ZERO`: 1,128 complete, 406 positive cumulative totals, but no source-backed qualifying opportunities in the 2025 H2 and 2026 Jan–Apr cohorts; thus a strict six-period positive requirement is structurally impossible, not a valid quiet-day alpha assessment.

**Important negative finding:** seven-day activity>=3 accepts ALL **1,721** registered V99 source-backed entry-variant exposures in the six covered cohorts. It does not meaningfully filter this historical source-ready population. The 24h active group accepts 1,628 of these exposures; quiet accepts 93 (5.4%). These counts are variant exposures, NOT independent brokerage trades. In both 2025 H2 and 2026 Jan–Apr, active and seven-day filters produce identical V90 account fingerprint for every one of 1,200 scenarios; quiet is all-flat. Do not treat the 7D gate's P&L as news alpha.

Highest retrospective six-cohort figure: `V97B-gap_followthrough_0940-04`, `balanced_35_100`, 1-second lag, 0-second dwell, **+$1,103.98** nominal stressed quote cash, identical for 24h-active and 7D gate: 41 modeled closed trades, 27 positive/14 negative; 2021 +$217.60, 2022 +$418.38, 2023 −$12.58, 2024 +$254.20, 2025 H2 +$82.68, 2026 Jan–Apr +$143.70. Two largest positives +$437.58 and +$391.16; excluding these, still +$275.24, but small sample and extensively searched. This was retrospectively picked from 3,600 settings, NOT validated as a market edge. Best frozen baseline combined six-family six-cohort 7D account loses **−$1,636.22**, best 24h-active combined loses **−$1,380.64**.

## Post-hoc prior-cohort-only chronology probe

An additional **post-hoc diagnostic** read only these already-studied V101 results. At each 2024, 2025 H2 and 2026 Jan–Apr evaluation boundary, it considered only configs with *all earlier cohorts source/settlement complete*, at least **10 earlier modeled closed trades**, strictly positive earlier total quote P&L, and no original source gaps. Its rank and tie-break used **earlier cohorts only**, never the chosen target cohort. No lookahead substitution was made for unavailable evaluation cash. There are three simple selector ranks: highest prior total; most profitable earlier cohorts (tie-break earlier P&L, then worst period); highest earlier worst-cohort P&L (tie-break earlier P&L and positive periods). Deterministic identity tie-break for ties.

| Selector | 2024 evaluation | 2025 H2 evaluation | 2026 Jan–Apr evaluation | Sum of separate-period P&L |
|---|---:|---:|---:|---:|
| Highest prior total | +$254.20 | +$82.68 | −$30.74 | **+$306.14** |
| Most positive prior cohorts | −$4.20 | +$82.68 | −$30.74 | **+$47.74** |
| Highest prior worst cohort | −$4.20 | −$125.80 | +$143.70 | **+$13.70** |

All three selections picked the **non-discriminating 7D gate** in their evaluation cohorts; thus this probe provides **zero positive evidence for a news-driven alpha improvement**. Only three short/uneven evaluation cohorts; selection rules devised after inspection of historical results; original V99/V100 research had already examined these markets. **NOT an untouched, preregistered, or statistically independent OOS profit result.** A $0 stay-flat comparator remains essential. The previous V100 selectors on the broader source-covered 2018–2026 development periods all lost money; do not substitute this post-hoc 3-period diagnostic for those results.

## Decision

V101 is **engineering-complete and historically audited**, not strategy-profitability validated. No more spending to re-acquire the same V99 option quote scopes or optimize 7D article count over this sample. Shift scarce development time toward a **structurally distinct** candidate such as the V51 SPY first-tick 0DTE opening-range breakout, but only when its signal clocks, independently captured 1s exact-contract option quotes and exit execution/sizing can be verified. Pre-register signal/exit policy on separate research cohorts, retain no-entry and provider-censored decisions, and preserve the protected master holdout. Public strategy return claims in V51 are third-party and not ATLAS-verified. Brokerage fills are **not** established by historical 1s NBBO.
