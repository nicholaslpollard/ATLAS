# ORB Stocks-in-Play Literature v2 — DEVELOPMENT closeout

Date: 2026-09-16  
Status: `COMPLETE_DEVELOPMENT_DIAGNOSTIC / NO_PROMOTION / PARKED_COST_SENSITIVE`  
Policy: `orb_stocks_in_play_5m_literature_v2`

## Frozen identity

- Strategy contract: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`
- DEVELOPMENT analysis contract: `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b`
- Completed analysis fingerprint: `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`
- DEVELOPMENT interval: 2016-01-04 through 2026-04-30
- Historical option P&L claimed: `false`
- Consumed-master reads: `0`
- Future-blind reads: `0`
- Provider reads: `0`
- Broker reads/writes: `0 / 0`
- PAPER/LIVE/promotion/confluence/option-trading authority: `false / false / false / false / false`

This result is diagnostic research only. The hypothesis was motivated with DEVELOPMENT evidence and literature overlapping the DEVELOPMENT era, so this run cannot self-validate or promote the strategy.

## Execution and population accounting

The accepted runner used 8 worker processes x 1 DuckDB thread. It materialized 2,695,914 prior daily PIT feature rows and completed all 482 opening groups fresh.

- opening five-minute snapshots: **4,957,662**
- eligible relative-volume rank pool: **62,516**
- daily top-20 selections: **40,606**
- doji abstentions occupying a rank slot: **261**
- directional candidates: **40,345**
- entered: **33,773**
- no entry: **6,572** (~16.29% of directional candidates)
- comparable: **23,412**
- same-minute entry/stop unordered: **10,361** (~30.68% of entered cases)

The selected full-path stage touched 261 accepted symbol groups and completed all 261 fresh.

## Frozen economic result

Aggregate comparable result:

- gross mean return: **+0.12%**
- primary 50-bps mean return: **-0.38%**
- stress 100-bps mean return: **-0.88%**
- mean path MFE: **1.27%**
- mean path adverse excursion: **0.41%**

Direction diagnostics:

| Direction | Candidates | Comparable | Gross | 10 bps | 25 bps | 50 bps | 100 bps | Median hold | MFE | MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LONG | 20,472 | 11,778 | +0.13% | +0.03% | -0.12% | -0.37% | -0.87% | 12m | 1.26% | 0.40% |
| SHORT | 19,873 | 11,634 | +0.11% | +0.01% | -0.14% | -0.39% | -0.89% | 12m | 1.28% | 0.43% |

The mechanism therefore shows a small gross directional edge in DEVELOPMENT, but the edge is fragile to ordinary friction and is already negative by 25 bps in both directions. It fails the frozen conservative 50/100-bps actionability assumptions by a wide margin.

## Underlying path / option-worthiness diagnostics

These are underlying-price path observations only; they are not historical option returns.

| Direction | Threshold | Favorable hit | Favorable first | Adverse first | Same-minute collision | Median favorable time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LONG | 1% | 34.31% | 33.99% | 2.21% | 0.02% | 6m |
| LONG | 2% | 18.22% | 18.18% | 0.25% | 0.00% | 17m |
| LONG | 3% | 11.00% | 10.99% | 0.12% | 0.00% | 29m |
| LONG | 5% | 4.71% | 4.71% | 0.03% | 0.00% | 48m |
| SHORT | 1% | 34.64% | 34.23% | 3.27% | 0.02% | 6m |
| SHORT | 2% | 20.17% | 20.13% | 0.28% | 0.00% | 17m |
| SHORT | 3% | 12.49% | 12.49% | 0.07% | 0.00% | 32m |
| SHORT | 5% | 5.51% | 5.51% | 0.02% | 0.00% | 70m |

The path distribution confirms that selected names can make fast, convex-sized moves: roughly one-third reach 1% favorably and roughly one-fifth reach 2% in the measured path. That does **not** rescue the strategy economics. The realized frozen entry/stop/EOD expression captures only about +0.12% gross on average, and no PIT option-chain replay exists to establish whether convex option expression would improve or worsen the economics after spread, theta, IV, liquidity and contract-selection effects.

## Diagnosis and disposition

1. **Primary failure mode: cost sensitivity / insufficient captured edge.** The gross mean is positive but too small to survive the frozen 25/50/100-bps friction grid. This is not an economically actionable baseline under the current ATLAS conservative policy.
2. **Execution-path ambiguity is material.** 10,361 entered cases are same-minute entry/stop collisions, about 30.68% of all entered cases. The frozen 0.10xATR14 stop is therefore very tight relative to immediate post-entry noise. That observation is diagnostic only; changing the stop after seeing this result would create a new version and cannot be called a v2 repair.
3. **Direction symmetry remains.** LONG and SHORT results are extremely similar, so the v2 result does not justify a post-result direction carve-out.
4. **Large/faster underlying moves exist but do not prove option profitability.** Move magnitude and speed warrant retaining the setup as an option-worthiness research reference, but actual option economics require accepted PIT option-chain/quote/IV evidence.
5. **No parameter rescue on this evidence.** Do not sweep relative-volume thresholds, rank counts, ATR stops, range length, entry delays or exits to manufacture a profitable v2. Preserve this result.

Disposition: preserve `orb_stocks_in_play_5m_literature_v2` and its completed DEVELOPMENT evidence, grant no promotion, and move on under the Strategy Development Cycle. A future materially different v3 may be motivated by this diagnosis plus targeted external research, but its rules must be frozen before new/untouched/prospective evidence is opened.
