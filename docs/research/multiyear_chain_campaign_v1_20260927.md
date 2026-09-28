# Multi-year historical-chain acquisition V1 — 2026-09-27

## What changes

The operator-supplied signed physical-source demand, original 2022/2025 source crosswalk, verified native stock opens and independently signed global local-overlap report are accepted. This implementation uses the **original signed D:-bound two option manifests directly**, not another repeat of the 14,902-stock selection, old 2,931-receipt global overlap audit, or 6,398 already completed 2022 quote body scan. Source identities and PIT strike envelopes remain unchanged.

Actual accepted population:

| Snapshot year | Original missing physical source keys | Previously verified complete global overlapping keys | Verified exact 404 |
|---|---:|---:|---:|
| 2021 eligible tail | 1,342 | 0 | 0 |
| 2022 uncovered original | 3 | 0 | 0 |
| 2023 | 1,473 | 36 | 0 |
| 2024 | 1,322 | 34 | 1 |
| 2025 | 3,434 | 1 | 0 |
| **Total** | **7,574** | **71** | **1** |

This physical-source workload is not all the history ATLAS needs. **4,138 earlier 2021 cases** remain outside the frozen five-year floor, with a rolling floor re-evaluated at each paid run. A new source outside the current provider's rolling window is necessary for those cases. No separate accepted 2026 replay-selection cohort has been established. The original 2022 **6,398 exact CALL quote histories remain pointer-reused**, not acquired again.

## Runtime

The new CLI makes an actual year-round-robin campaign from the 7,574 signed missing physical keys. Preview with no authorization is local only. With all three explicit operator confirmations, a positive request ceiling and an observed-credit ceiling, the same command:

1. Checks only these 7,574 exact new-key cache paths for completed local receipts or unresolved intent before doing anything billable; skips all original 71 overlapping and 6,398 2022 quotes without rereading their bodies. It never sends an API GET against any completed original physical key.
2. Rechecks the current rolling five-year date floor and keeps slipped-out 2021 requests as explicit gaps, not mistaken 404s. It does not invent protected 2026 selections.
3. Starts year-balanced waves (2021, 2022, 2023, 2024, 2025), using up to 24 bounded network workers, an explicit total ceiling, 500-credit reserve after the first authoritative provider response, per-wave conservative in-flight credit and raw-body reservations, and a D: secondary budget.
4. Uses the accepted global cache's **intent-before-GET, exact raw body, receipt SHA, row/OCC/strike/expiry checks**. An exact 404/no_data response becomes a separately signed exact-query-only sidecar only when strict original zero-credit proof is satisfied. Any uncertain attempt, invalid response or quarantine ends further waves; already in-flight workers finish writing their own evidence. No hidden retries.
5. Saves a checkpoint after each complete wave, prints source/credit/D: progress, and resumes later from exact immutable receipts rather than spending credits again. It never performs historical contract selection from future quote activity.

There is no full-corpus post-campaign validation gate in the normal downloader and no external source is inferred from used SSD bytes. It is **chain acquisition**, not historical executable option-price, Greeks, or portfolio-return authority. The next code stage must select policy-frozen OCC identities from these saved chains, acquire each *full exact-symbol EOD quote history once*, add puts and alternate expiries only where the strategy calls for them, then build the offline common-clock source and realistic account-level simulator. Actual same-minute entry demands timestamped historical intraday option bid/ask; EOD records are not retroactively a 09:35 fill.

The user's requested research objective is **exceptional but empirically established risk-adjusted compounding**, never a target percentage or target small-account balance. Loss-making results and abstentions are recorded. Training folds, regime robustness, costs, drawdown and protected forward evidence remain separate.

## Operator handoff

Free preview:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Pull failed.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_chain_campaign_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Multi-year preview stopped.' } }
~~~

To actually acquire accepted source gaps, the operator must explicitly run with --max-new-requests, --max-observed-credits, --workers (maximum 24), --authorize-provider-reads, --confirm-paid-starter, and --confirm-private-internal-use. A single run can have up to 7,574 physical requests, but the authorized credit ceiling and current available credits determine a safe smaller campaign. The user must not start another provider job concurrently. A completed partial result resumes only unresolved genuinely new keys on the next authorized invocation; an ambiguous prior attempt blocks the campaign instead of silently retrying.

**2021 rolling floor caveat:** On 2026-09-28 the earliest available date may advance from 2021-09-27 to 2021-09-28. Those 23 September 27 physical requests are marked as rolled out when the newer floor applies. Do not silently backdate query dates or remove the stock cases.

## Inputs and authority

- Signed source demand 7890c81e62905307fb1cc2c1bf3f2205eece3dfdf04b712ee1b8a09d419f084c
- Signed accepted global overlap 056c70bc7163b793b3c4cc2c83bee48b19272d95171f8dee8c9d296b5c65d30b
- Verified source-only operations; no strategy promotion, PAPER, LIVE or broker/order authority.


## Operator's actual 1,986-credit daily balance: 1,500 acquisition cap / 486 reserved

The operator explicitly chose to make up to **1,500 observed credits** available for this source campaign, preserving **486** for the next source-driven simulator preparation. The CLI now exposes `--min-remaining-credits 486`; the default remains 500 when omitted. The downloader retrieves a fresh provider balance from its first paid GET before widening concurrency, and shrinks the last batch as the credit floor or 1,500-credit ceiling approaches. It conservatively reserves **two potential credits per in-flight GET** and may therefore stop slightly short of exactly 1,500 spent. Provider headers, not the operator's earlier balance report, remain authoritative. There is **no additional voluntary 500-credit buffer** on this explicitly authorized run. If the account has been used elsewhere, the runner leaves at least the configured floor according to its last observed account credits, subject to in-flight exposure. No other paid job should share the account simultaneously.

Single-line PowerShell, only after merged CI:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_chain_campaign_v1.py --max-new-requests 7574 --max-observed-credits 1500 --min-remaining-credits 486 --workers 24 --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use; if ($LASTEXITCODE -ne 0) { throw 'Acquisition stopped; preserve original receipts and paste full output. No blind retry.' }; $d = Get-PSDrive -Name D; Write-Host ('D: free space: {0:N2} GiB' -f ($d.Free / 1GB)) }
~~~

This is an **acquisition-only** command. It does not silently spend the 486 credits on simulation, nor pretend that stock/news/options strategy replay or conditional on-demand quote fetching has already been implemented. Full quote-history acquisition and an offline simulator are the next implementation steps; tomorrow's fresh provider balance supports a separately authorized continuation.
