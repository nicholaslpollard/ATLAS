# ATLAS V79 original options exit events and V80 sell-limit price protection gate

**Evidence date:** 2026-10-31. **Input:** operator-uploaded V79 original journal ZIP from user-run V77, containing **244 immutable compressed full event journals** (61 original entered opportunities × two policies V74 control/runner × 1s/3s action delays) and six signed monthly V76 manifests. This is source-linked historical **quote reference**, not Webull or Alpaca actual order execution. An independent standard-library offline auditor checked six monthly source manifest signatures; all 244 compressed SHA-256 hashes; all 244 signed outer V76 and nested V74 journal fingerprints; parent option archive and signal SHA identity; requested quantity vs displayed action-side bid size; causal action time; journal quote + fee P&L mathematics. All passed. Summary and reproducible script are available as user artifact `atlas_v79_independent_event_audit_20261031.zip` (not committed to repo).

## Two high-signal cases

**2025-07-30** original 0DTE SPY long call, 3 contracts, original entry at 09:46:02 ET for total modeled $499.95: control V74 held at qualified 11:21:59 quote bid about 1.13 / ask 1.14, displayed bid size 242. At 11:22:00 through 11:22:31, source journal reported 32 consecutive invalid bid/ask-size quotes. V74 control returned `INVALID_QUOTE_BLACKOUT_EXCEEDED`, **not an observed sale or proven $0 cash loss**. Runner had already generated its -35% stop at 11:12:02, action 11:12:03 BID 1.10, bid size 142 for three contracts, yielding modeled **-$171.90**. This candidate closed *before* the original blackout; never substitute its exit for the censored control trade.

**2025-08-20** original long 0DTE SPY call four contracts, entry 09:41:02 ET, original debit $442.60 including modeled fees. The control +100% profit target triggered 09:51:20 bid 2.21, action 09:51:21 bid 2.19 (displayed size 101), modeled **+$430.80**. The +150% runner target triggered 09:53:43 bid 2.79, action 09:53:44 bid 2.79 (displayed size only **9 contracts**), modeled **+$670.80**—$240 improvement versus control on this date. The preceding runner valid source event at 09:53:42 recorded BID 2.47 / ASK 2.49, so the next trigger BID jumped to 2.79. V76 original *trigger/action event receipts* do not preserve full ASK and size at the precise trigger or ASK at action. **Do not certify those quotes as erroneous or full limit-order fills without reading the locally retained original ThetaData exact tape and broker-independent order-state evidence.**

## Complete-event results and price protection

244 originals contain **242** modeled sell-to-close action references, two quote-unresolved control July30 cases, 242 EXIT_INTENT events, 244 original entries, **94** invalid quote events, **10** logged insufficient displayed quote-size events and ~472,928 held/qualified EXIT_REVIEW observations. Source lineage and P&L/fees reconcile. They demonstrate causal quote-observation replay, not historical order execution.

The existing V74/V76 model books the action-time BID as quote-reference sale even when lower than trigger BID. A DAY sell-limit fixed at the trigger bid would no longer be **immediately marketable** when the action BID falls. Any decision to lower that limit requires an explicitly bounded new price decision, fresh quote and order ack. The new independent pure function `packages/simulation/spy_v80_exit_price_protection_shadow.py` evaluates signed V76 journals for 0, 0.5, 1 or 2% maximum adverse BID drift and returns **quote-only states, never broker fills**. `scripts/run_spy_v80_signed_exit_price_protection.py` verifies the entire source ZIP and writes signed 976-case (244×4 bands) marketability results without source GETs or broker requests.

At a **1% hypothetical adverse price concession band**:

| Exit research policy | Quote supports original limit (not fill) | Reprice within band, not executed | Band exceeded, block | Original unresolved |
|---|---:|---:|---:|---:|
| runner 1-second | 39 | 7 | 15 | 0 |
| runner 3-second | 36 | 5 | 20 | 0 |
| V74 control 1-second | 41 | 9 | 10 | 1 |
| V74 control 3-second | 43 | 1 | 16 | 1 |

These are diagnostics, **not six-month cash returns**. Marketable quote ≠ historical broker acknowledgement/fill. Even a fully displayed bid size does not guarantee executable liquidity or absence of cancellations, venue order priority, different options order capabilities or partial fills.

Independent price stress (retain original option entry, original modeled fee and quantity, apply only *additional hypothetical* adverse haircut to exit BID, and recalculate quote-reference P&L):

| Extra adverse exit BID price | Runner 1s | Runner 3s |
|---|---:|---:|
| 0% | +$492.40 | +$444.40 |
| 0.5% | +$359.95 | +$312.21 |
| 1% | +$227.56 | +$180.04 |
| 2% | -$37.28 | -$84.32 |
| 5% | -$831.80 | -$877.40 |

Runner remains **unpromoted**: 2025 H2 +$492.40 relies on an August20 +$670.80 single modeled win, leaving -$178.40 excluding that outlier; two losing months, nonzero weekly losses and no broker or portfolio cash validation. H2 no longer constitutes uninspected test data.

## Next complete simulator acceptance gates

1. Preserve immutable V74/V76 historical quote-reference outputs. V80 must never modify them or promote any experimental result to live options. The new V80 report intentionally has `credited_cash_from_shadow=None` and `actual_broker_fills=0` for **all** input cases, including those with action BID >= original sell limit.
2. For a true forward simulator engine, create a separate broker-neutral option order lifecycle with `intent → fresh quote → proposed limit → submitted → broker ack → partial/filled/cancelled/rejected/unknown` states, all signed with original time, amount, contract, quote BID/ASK, sizes, spread, action drift, fee/quantity, delay, position state, and broker account reconciliation. Unknown broker outcomes are not safe to retry or cross-route; Webull first and Alpaca *manually* selected fallback only. Do not credit realized cash until actual broker fill evidence exists.
3. Never infer physical exercise, ITM intrinsic cash settlement, option order market support, account buying power or forced broker expiry liquidation from quote source. Record official XNYS early closes, 0DTE and broker-specific time cutoffs as separate static information, not guaranteed liquidation.
4. Once this order-evidence contract is available, advance beyond **one M/W/F opening-range entry** to independently causal entry families and stock fallback, dynamically acquire/persist every new selected contract's exact source with cache-first no arbitrary cap; run one strategy at a time and then a shared capital/risk simulator with prior-only training and uninspected time windows. Report all skipped/considered trades and weekly/monthly/annual net viability.

No extra provider or broker calls are authorized by this research. [V78 H2 economics](spy_v78_original_quote_2025h2_independent_economics_20261031.md).
