# MarketData x Massive Sparse-Activity V2 — First-Run Acceptance (2026-09-25)

## Result and provenance

**SPARSE_ACTIVITY_CONCORDANCE_CONFIRMED** — all preregistered V2 checks passed.

This records the user's complete first-run workstation output. It is not a cloud
reproduction and does not make another authenticated provider call.

- Contract fingerprint: `28b78b39b3cb1b40fce2e48e325c439f4919e16c28333b3180d913d76707a325`.
- Run ID: `20260925T184421Z`.
- Evidence fingerprint: `398ca760a7e05126e18008c6e7c09fc2f9d03e8a07b5a9a95e0282891d4c2d69`.
- Workstation original: `data/research/provider_qualification/marketdata_massive_sparse_activity_v2/20260925T184421Z/report.json`.
- Selector: frozen third-farthest OTM call from restricted historical chains.
- Planned and performed logical reads: 12 MarketData chains, 12 MarketData
  selected-contract quote histories, 12 Massive exact-contract day aggregates.
- MarketData credits observed: 24; last reported remaining: 9,966.
- Terminal error: none.

## Complete first-run sample

| Root | Anchor date | MD sessions | Zero-volume | Positive-volume | Massive daily rows | Mismatches |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| GLD | 2025-10-20 | 9 | 1 | 8 | 8 | 0 |
| SLV | 2025-11-17 | 8 | 0 | 8 | 8 | 0 |
| GDX | 2025-12-15 | 8 | 0 | 8 | 8 | 0 |
| USO | 2026-01-26 | 9 | 0 | 9 | 9 | 0 |
| XLE | 2026-02-23 | 9 | 3 | 6 | 6 | 0 |
| XLK | 2026-03-23 | 9 | 6 | 3 | 3 | 0 |
| XLY | 2026-04-20 | 9 | 8 | 1 | 1 | 0 |
| XLP | 2026-05-11 | 9 | 2 | 7 | 7 | 0 |
| XLU | 2026-06-22 | 9 | 3 | 6 | 6 | 0 |
| XLI | 2026-07-20 | 9 | 0 | 9 | 9 | 0 |
| XLV | 2026-08-10 | 9 | 6 | 3 | 3 | 0 |
| XLRE | 2026-09-14 | 9 | 9 | 0 | 0 | 0 |
| **Total** | | **106** | **38** | **68** | **68** | **0** |

- Zero-volume sessions: 38 over 8 anchors; every session lacked a Massive daily bar.
- Positive-volume sessions: 68 over 11 anchors; every session had a Massive daily bar.
- Activity concordance: 100%.
- Zero-volume with Massive bar: 0.
- Positive-volume without Massive bar: 0.
- Invalid volume sessions: 0; extra Massive dates: 0.
- All ten frozen pass checks: true.

## Interpretation and limits

This is **activity-state concordance** on a fresh mixed-activity sample. It is
not a quote-price comparison. In particular, a MarketData `last` persisted on a
zero-volume session is **not** independently validated as a same-session trade
price and must not be used as observed execution evidence.

The failed first sparse confirmation, run `20260924T033435Z`, remains
`SPARSE_ACTIVITY_CONFIRMATION_FAILED` because it had only 18 positive controls
against a frozen minimum of 20; its 100% observed concordance is retained without
retroactively declaring the run passed. Disjoint price validation V1 and V2 also
remain failed under their original preregistered criteria.

See the separate evidence-synthesis record for the permissible **joint descriptive
interpretation** of the earlier 53 positive-volume price comparisons and this fresh
106-session activity experiment. No claim of broad EOD option price or fill
authority is established by this record.

No new strategy outcome, selector, predictor, portfolio, PAPER, LIVE, broker,
order, promotion or confluence authority is created. This is provider/source
semantics only. The Strategy Evidence Register remains unchanged.
