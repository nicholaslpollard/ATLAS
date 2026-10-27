# V28 — Explain SPY exact-contract historical exit quote attrition before targeted data acquisition

## Evidence that triggered this change

The user executed the fully green V25–V27 workstation regression set (21 passed) and the V27 complete retrospective original-source five-horizon read with **zero ThetaData/provider/broker calls**.

All five horizons used **the same original 4,862 candidate entry pairs** (not the frozen one-pair ATM SPY strategy):

| Fixed exit review | Matched originally entered pairs | No review source | No qualifying exact exit pair | Conditional ask-to-bid mean after $0.65/side contract fees |
|---|---:|---:|---:|---:|
| +1 XNYS session | 1,967 | 29 | 2,866 | −3.533890% |
| +2 | 1,605 | 33 | 3,224 | −4.645116% |
| +3 | 1,147 | 46 | 3,669 | −7.187114% |
| +4 | 1,087 | 41 | 3,734 | −9.054241% |
| +5 | 780 | 0 | 4,082 | −12.096621% |

Report fingerprint: `19928e1606f7c5fafae09603236413ebeb44969cf2e3a719d238af2375440bd3`.

**Interpretation limits:** all values are **conditional on retaining a later complete qualifying pair**, include many strikes the frozen SPY ATM rule would never select, use 10:00 snapshots rather than 10:01 executable order events, and have no model IV/PIT OI/underlying spot account lifecycle. They do not establish portfolio returns, strategy profitability, theta/vega attribution or profitable parameter choice. The disproportionate unmatched population makes survivorship conditioning material.

The first four days had only 29/33/46/41 candidate pairs associated with unavailable source responses; by five days every source was available but 4,082 pairs lacked a qualifying exact review. **That is a retrospective source-matching fact, not evidence that ThetaData is missing the actual options or that quote staleness versus strike truncation is resolved**. `strike_range=2` is one plausible cause needing direct evidence.

## What V28 implements

`packages/data/options_native_exit_coverage_attribution_v28.py` is a strictly **offline explanatory read** reusing V26 immutable receipt, original gzip/SHA provenance, entry V14 indices, and V27 original cohort. For all 1–5-session fixed reviews it classifies each original candidate pair into precisely one reason:

- NO_REVIEW_SOURCE: no preserved eligible source for the review time
- EXPIRED_AT_REVIEW: exact original contract expired before the required review
- BOTH_RIGHTS_ABSENT, CALL_ABSENT, PUT_ABSENT: contract identity absent from **retained response only**, not proof it was absent from the market
- BOTH_QUOTES_REJECTED, CALL_QUOTE_REJECTED, PUT_QUOTE_REJECTED: exact contracts observed but failed V26 independent quote quality gates
- PAIR_CLOCK_SKEW: both individually qualified quotes observed but timestamps diverge by more than 1 second
- MATCHED: exactly the same V26-accepted complete option pair

Individual quote-quality reasons include stale, no two-sided price, no positive displayed size, and spread greater than 15%. Structural defects (crossed prices, invalid timestamp) still fail closed rather than being accepted as mere noise. V28 checks its MATCHED classification against `_pair_observations` from V26 and verifies denominators **equal 4,862 on every horizon** on the user's preserved source corpus. No quote is substituted, and extra beyond-window DTE rows stay retained.

Source-read data remains bounded in the existing V26 LRU cache rather than materializing all eight years into RAM; original archives are not modified. V28 preregisters with the same hash-chained historical research ledger **before** any future quote outcomes are read. Its counts of absent contract rights across later response days are *diagnostic leads only*, not paid acquisition permission or a pre-authorized download plan.

## One workstation command after successful CI and merge

```powershell
$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main' }
if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
$py = '.\.venv\Scripts\python.exe'
& $py -m pytest -q tests/test_options_native_exit_coverage_attribution_v28.py tests/test_options_native_fixed_hold_quote_sweep_v27.py
if ($LASTEXITCODE -ne 0) { throw 'Targeted tests failed' }
& $py -m scripts.run_options_native_exit_coverage_attribution_v28 --output data/research/spy_exact_contract_exit_coverage_v28.json
if ($LASTEXITCODE -ne 0) { throw 'Offline V28 diagnosis failed; preserve console output' }
```

No ThetaData/broker calls. On first use, the append-only trial ledger adds V28 registration. If the JSON filename exists, choose a new filename; it never overwrites.

## Required follow-on simulator milestone

The purpose of V28 is **one fast decision**, not a new multi-week analytics project: either many matching exact rights are absent from retained `strike_range=2` source responses, justifying a **small targeted contract/date request pilot during the active subscription**, or the rights exist but fail age/spread/size/skew, in which case additional chain re-downloads will not automatically fix execution economics.

Then bind the original SPY pilot's entry-available 10:00 spot, prior 20 economic close-to-close returns, publication-time corporate actions, OI and dated rates/IV; preselect **one** earliest-DTE/nearest-spot ATM pair at each weekly entry, test its variance signal and dynamic exit in a separately typed hypothetical execution/account engine. Historical 10:00 quote observations are not actual 10:01 fills; unknown terminal marks must remain unresolved. Preserve every tested version and keep new independent forward evidence for profitability claims. Only then integrate with V25's broad parameter and shared-capital machinery.
