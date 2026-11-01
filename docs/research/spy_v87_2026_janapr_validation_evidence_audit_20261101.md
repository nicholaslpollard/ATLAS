# V87 completed Jan–Apr 2026 temporal validation — independent upload audit (2026-11-01)

## Immutable evidence and audit scope
On 2026-11-01 local workstation, commit `3fafa826fd11b238b0c37e610499fd5a4a0560f0` completed 27 focused tests and ran the **already-frozen** V84 → V85 → V86 pipeline on January 1–April 30, 2026. Original SPY monthly stock source SHA audit and ThetaData exact-source acquisition were completed on 2026-10-31 in V83: **82** XNYS sessions, **246** three-family candidate decisions, **77** original 0DTE option query requirements and all **77** provider archived. No V87 new provider calls or broker orders.

User uploaded `spy_v87_validation_2026janapr_20261101_080231.zip` (3.6 MB) for offline verification. Independently checked ZIP CRC, **all 11 top-level report SHA-256 signatures**, all **462 V84 gzip original trial SHA-256/signatures and fields**, all **1,848 V86 gzip original limit-recheck SHA-256/signatures and reference fields**, all **48 embedded signed V85 ledgers**, all **96 embedded signed V86 ledgers**, all **96 V86 comparison-to-ledger fingerprints**, and top-level V87 → V84/V85/V86 report/portfolio links. **0 audit mismatches**.

Original 2026 V83 source ZIP and original 1-second source quote *bytes* were not included in the V87 upload. The signed V87 output **attests** 77 local original V38 quote source SHA matches, but a complete *independent* raw source audit requires that separately signed V83 source ZIP and, for raw quote reproduction, the workstation original V38 archives. Do not claim the 2026 source bytes were independently rehashed from this ZIP.

- V87 summary SHA `3b7cf82458c167cb89f07039fb06fd35314392a4958f4d29828859b884b15716`
- Parent V83 campaign summary SHA `9ffcf8ef6492e2968fe9142b780117aedf59ac782813e4dfb32e6075915deebf`
- V84 replay summary SHA `a708d74abdb04171046a244d41f9f94d4895332ea7c1db5551957738d1ae88a5`
- V85 account ledger summary SHA `56a5a6f5126847577707ec2334a0494cc0bf0a87752483819279f2cceb83c125`
- V86 recheck summary SHA `a31dc9421448d8e5e00bae9aa3e66bdcfc9e931e4aa688b58c21e8ba3847cbac`
- V86 account comparison SHA `47a1385b30d5a81df3e99fd092929e5164f4047ffad67baadad6fba25fd6310c`

## Preregistered primary result, frozen BEFORE 2026 scoring
Exactly `failed_breakout_fade_0940 / balanced_35_100 / 3-second action lag / 10-second original limit rest / adverse 2% observed BID haircut`, same quantity and cash rules as 2025 H2, **never retuned after 2026 inspection**.

- 30 independently considered historical entry opportunities; **13 original NO_ENTRY**, **17** hypothetical quote-reference entries and **17** same-session quote-reference exits; 0 cash-capacity conflicts and 0 unresolved modeled exits. There are **zero verified historical broker fills**.
- Primary stressed quote-reference P&L **+$883.70**, unstressed **+$1,047.00**; $25,000 initial nominal research cash, stressed terminal cash-reference **$25,883.70** (+3.53% of initial nominal balance over four months); all dollar results are hypothetical, not real tradable returns.
- Monthly 2% stressed closed quote reference: **Jan +$563.24** (6 exits/8 original opportunities), **Feb -$141.08** (2/8), **Mar +$209.72** (5/7), **Apr +$251.82** (4/7). 11 profitable quotes, 6 losing; quoted maximum flat-to-flat completed-trade cash drawdown **$438.30** (not full mark-to-market risk).
- The **largest two favorable quote outcomes** were +$471.52 (Jan 22, original fixed limit marketable at action) and +$381.00 (Mar 25, **hypothetical cancel/reprice quote shadow**). Together **+$852.52**, or **96.47% of net hypothetical result**. All other 15 outcomes combined contributed **+$31.18**. This is strong tail-win dependence; no claim of consistent per-trade edge.
- Among the 17 entries, original trigger limit was quote-marketable at action for 13 (combined **+$700.98**); one later limit rest became quote-marketable (**-$180.92**); three exits required hypothetical cancel/reprice (combined **+$363.64**). These are **exit-time classifications, not causal entry signals**. Do not drop these trades post hoc to inflate returns.

## Simultaneously frozen controls and 2025 H2 comparisons

| Scope | 2025 H2 development (6 mo) | 2026 Jan–Apr later period (4 mo) |
| --- | ---: | ---: |
| Preregistered failed-breakout fade | +$971.68 | **+$883.70** |
| Opening-range continuation | -$63.74 | **-$674.10** |
| Gap fade | -$141.40 | **-$478.96** |
| Three-family one-slot combined account | +$778.14 | **-$325.82** |

All values use same **balanced_35_100 / 3s / 10s / adverse 2% BID haircut** conditional quote-reference model and fees. Different months, frequencies and candidate sources; not independent verified execution. 2025 reference V86 original evidence `spy_v86_exit_recheck_2025h2_20261031_223547.zip` was separately re-read for consistent denominator and ledgers: development fade 39 modeled entries / 51 original opportunities, 22 positive / 17 negative, monthly +415.98/+117.84/+127.94/-104.22/+662.46/-248.32; top two favorable quotes +$810.52 (**83.41% of net 2025 H2 quote return**). Remaining 37 trades contributed +$161.16. The positive later-period results **do not** remove the concentration risk seen in development.

Combined 2026 January–April account is negative **-$325.82**, with 49 accepted quote-reference entries, 25 rejected original entries and 3 blocked by position capacity. Combining the three families did NOT validate and **must not be promoted**. Opening-range continuation and gap-fade are not qualified under the frozen policy; no automatic strategy parameter tweaking on this validation result.

## Limits / gating decisions
1. **FAILED-BREAKOUT FADE**: positive later temporal validation and candidate for additional *pre-frozen* testing, but small sample (17 2026 modeled entries), strong tail-win dependence, unverified exchange fill/market impact, size-only displayed quotes and hypothetical cancel/reprice. **NOT PROMOTED** to live trading or as proven expected profit.
2. **ORB CONTINUATION / GAP FADE / COMBINED**: negative later-period controls. **NOT PROMOTED** and do not permit them to dilute the targeted primary strategy automatically.
3. **Protected master holdout 2026-05-12 through 2026-08-11**: **not accessed**. Future exposure requires an explicit, frozen independent test plan, minimal researcher degrees of freedom and no post-result edits. Jan–Apr is later-period validation, not a guaranteed virgin holdout because some prior source audits covered Jan–Apr.
4. **Source proof boundary**: original V87 archive stores derivative SHA references and signed journals, *not* original option quote tapes and *not* the original V83 ZIP; source byte re-verification remains dependent on V38 local cache.
5. **Metadata clarification**: the standalone V86 summary still contains legacy `in_sample_development_only=True` even within this V87 validation run; V84 summary `in_sample_development_only=False` and V87 frozen validation report correctly mark the 2026 later period. This is a V86 metadata-label defect only, not a demonstrated change in trades or cash logic; do not silently rewrite immutable signed reports.

## Next meaningful work
The next research gate must emphasize original-order marketability, hypothetical fill assumptions, overconcentration and *independent forward evidence*; do not optimize 2026 for a different exit/rest combination. At minimum, require additional independently timed source periods or actual clocked paper-order observations (never fake broker fills), severe extra slippage and outlier-deletion robustness checks, and model expiration/assignment risks explicitly before any live-trading proposal. Maintain the one-slot $25,000 model and original frozen decision clock in all such comparators.

Status: **2026 temporal validation PASS as source-linked, signed offline research; NOT a strategy-promotion pass**.

## Extra execution-price fragility sweep (post-validation diagnostic; NOT a strategy choice)

Independent analyst recomputed each original **preselected and signed trade** using its original logged option exit BID, signed action quantity, original entry debit and $0.65 per-contract exit fee. The original 2% stressed P&L of 2025 H2 and 2026 Jan–Apr was reproduced **exactly cent for cent** before evaluating any additional haircuts. Entry opportunities, no-entry rejections, exit action clocks, quantities, option strikes, monthly periods and strategy configuration remain unchanged. Added haircuts are **post-result execution sensitivity diagnostics only**.

| Adverse exit BID haircut | 2025 H2 39 exit quotes | 2026 Jan–Apr 17 exit quotes |
| --- | ---: | ---: |
| 0% (observed BID reference) | +$1,303.60 | +$1,047.00 |
| 2% (preregistered case) | +$971.68 | +$883.70 |
| 4% | +$639.76 | +$720.40 |
| 6% | +$307.84 | +$557.10 |
| 8% | **-$24.08** | +$393.80 |
| 10% | **-$356.00** | +$230.50 |

There are 118 modeled contracts across 39 accepted 2025 entries and 40 modeled contracts across 17 accepted 2026 entries (contract count here counts *trade quantities*, not unique listings). The results still rely on **full hypothetical exit of each modeled quantity** at the registered historical quote minus chosen haircut, and therefore do not establish actual fills, queue priority, bid depth throughout that quantity, exercise loss, or live slippage distributions. The 2025 H2 result turns negative by an 8% haircut; neither period passes a true fill-verification gate.

