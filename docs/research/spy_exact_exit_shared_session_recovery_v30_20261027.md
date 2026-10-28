# V30 — Shared-auth exact SPY exit-source recovery, source-only

## Why V30, not another all-strikes download

The user has an active ThetaData Options Standard subscription and just ran V28 successfully: **3,999 of 4,862 original candidates have BOTH rights absent from the 5-session retained broad surface**, accounting for almost all missing observations. V28 enumerated 33,522 absent historical contract-right/date references over **all possible** entry options. Downloading all 33,522 would waste active subscription time, memory and attention, and would compound retrospective many-strike selection bias.

V29 (the preceding pull request) instead uses the verified original accepted SPY minute stock source to select **one provisional original pair per weekly entry** based on the frozen earliest-expiry/nearest-spot/lower-strike-tie rule, with no fallback after bad selected quotes or unavailable future exits. Its exact missing rights are bounded to **411 weeks × 5 sessions × 2 rights = 4,110 maximum**. The historical availability of SPY 09:59 raw minute spot is still unknown; no strategy entry signal, option IV/OI, rate/dividend, fill, portfolio mark, or account performance has been qualified.

## Implemented acquisition pathway

`packages/data/options_native_spy_exact_exit_source_campaign_v30.py` parses the V29 report, validates its content fingerprint, 411 case selection identities, preview-only status and each missing original CALL/PUT right, then executes one of two modes.

**Preview mode:** reads bounded existing V30 receipts and lossless gzip fingerprints, counts `UNATTEMPTED`/archived/no-data/provider failure/uncertain dispatch and makes **zero ThetaData calls**.

**Paid `--run` source-only mode:** uses the pinned ThetaData SDK 1.0.12 isolated Python worker. The provider client has a new strict `option_at_time_quote_exact_shared_session_batch` interface for exact `symbol=SPY,date_et,time_of_day_et=10:00:00.000,expiration,strike,right=call/put` requests. It reuses the existing V24 worker `batch_option_at_time_quote_shared_session` request, allowing **four independent SDK quote GETs using a single authenticated ThetaClient session**. The old frozen broad `max_dte=45,strike_range=2` batch surface retains its original validation untouched.

The campaign authenticates **before creating any started receipt**. Each exact request writes an immutable STARTED receipt before batch dispatch. Raw provider-normalized content is preserved losslessly in an immutable SHA-256 verified gzip file, and each completed request writes one immutable TERMINAL receipt bound to the source plan/STARTED receipt fingerprint. No previously started uncertain request or prior terminal failure is retried automatically; a separate versioned recovery authorization/plan is needed for such identities. A source without an original response remains unaccepted. Mismatched expiry, strike, right, SPY symbol, out-of-review timestamp, crossed quote or unexpected source schema is preserved as invalid diagnostic evidence, never promoted. A documented `explicit_no_data` response remains terminal no-data rather than fabricated price. Source version, SDK provider transport/environment identity and immutable SHA proof are required, but original 10:00 quotes do NOT authorize 10:01 fills. Entire V24 historical source inventories remain unchanged.

Storage uses the existing conservative V24 external SSD meter (full audit every 32 launches, live disk-headroom check on every request, worst-case 16MiB-class response reservation and floor). A hard provider authentication/rate-limit/status failure or repeated mismatched source stops *new batches* while retaining receipts for already dispatched IDs. The campaign is resumable and supports a per-run `--max-calls` budget without extra prompts; `--run` can continue all eligible IDs automatically, but ambiguous calls never get retried.

## One workstation command after BOTH PR #396 and #397 merge green

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
  if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS not on main' }
  if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
  git pull --ff-only origin main
  if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
  $py = '.\.venv\Scripts\python.exe'
  & $py -m pytest -q tests/test_options_native_spy_physical_spot_exact_demand_v29.py tests/test_options_native_spy_exact_exit_source_campaign_v30.py
  if ($LASTEXITCODE -ne 0) { throw 'V29-V30 targeted regression failed' }
  & $py -m scripts.run_options_native_spy_physical_spot_exact_demand_v29 --output data/research/spy_one_pair_exact_exit_demand_v29.json
  if ($LASTEXITCODE -ne 0) { throw 'V29 original source selection failed' }
  & $py -m scripts.run_options_native_spy_exact_exit_recovery_v30
  if ($LASTEXITCODE -ne 0) { throw 'V30 preview failed' }
  & $py -m scripts.run_options_native_spy_exact_exit_recovery_v30 --run --progress-every 25
  if ($LASTEXITCODE -ne 0) { throw 'V30 source campaign stopped; preserve output' }
}
```

The first executable inspection of these sources is a **historical quote collection step, not a simulator run**. The script starts paid requests only at `--run`. No minimum authorization phrase is required when the user directly runs the paid `--run` command. For safety or testing, omit `--run` and `--max-calls` can cap calls.

If the V29 report path already exists, use a fresh output filename and pass that new filename with `--plan` to V30. Do not delete or rewrite prior report/source receipts to rerun a query.

## Next research-to-simulator integration (code, not more bulk downloads)

Merge recovered V30 exact original quote rows *as a separately typed diagnostic evidence source* with the source-verified broad original exit quotes. For each originally selected CALL+PUT contract, evaluate chronological spot-driven entry, prior-20 economic return/IV variance signal and frozen dynamic exits. Require point-in-time stock bars, timestamp availability or a clearly labeled bounded historical-latency model, standard OCC deliverables, prior OI, corporate-action/rate/dividend inputs and option order eligibility. Reserve capital from entry, mark or carry unresolved positions at each review session, and never turn a merely observed 10:00 bid/ask quote into an actual 10:01 fill. Mark terminal account equity `null` if a required position cannot be marked/settled; preserve weekly/monthly/yearly and cost/drawdown comparisons with independent forward evidence.

The active Standard window should first secure the needed exact original contract observations. Profitability cannot be claimed from V27/V28 conditional option quote returns or the mere availability of V30 source archives.


## 2026-10-28 V33 correction — two consecutive ambiguous four-request batches

User's first V30 paid session archived 80 exact-right sources, then one entire four-request batch was STARTED but no complete worker batch result returned. On the next manually initiated V30 session, the first four-request batch again stopped ambiguous with **zero new completed sources**. Current immutable state: **80 archived**, **8 uncertain started-only**, **2,264 unattempted**, total 2,352. No proof exists that either ambiguous batch reached ThetaData; all eight identities remain excluded from all automatic retries.

**Confirmed local implementation defect:** the original V30 exact-provider client used a regular expression with *two literal backslashes* before the decimal point, incorrectly rejecting legitimate fractional strikes (e.g. `100.5`). The V30 plan itself correctly accepted those decimals. The provider client performed that validation **inside the batch call, after STARTED receipts had been written**, so one local validation error could make four unused identifiers appear ambiguously dispatched. This bug is a plausible but not confirmed explanation for the two user-observed interruptions; the original error log did not expose the query strikes or worker exception type.

V33 corrects and regression-tests the single-backslash decimal regex. It factors exact SDK request normalization into a **pure no-provider pre-dispatch validator** called by the campaign BEFORE any new STARTED receipts, using exactly the same validator inside the provider batch function. Invalid local requests now block without losing any identities or making historical provider calls.

Second independent root-cause class: the four-result SDK adapter used to raise a whole-batch exception if just one ordered returned item was malformed, had inconsistent no-data flags or could not be JSON-canonicalized (e.g. nonfinite numbers). V33 instead emits a **terminal per-right sanitized ThetaDataError** only for that item and preserves the other three original returned observations/archives. A failure in the worker's entire ordered response still remains genuinely ambiguous; V33 never fabricates completion or retries any affected ID.

**Optional adaptive recovery** via V30 `--run --adaptive-recovery` (after V33 CI/merge): on the **first** genuinely ambiguous ordered four-query batch, keep its 1–4 STARTED IDs uncertain, restart a fresh authenticated isolated SDK worker without making an historical request, then test **16 NEW distinct unattempted IDs one-at-a-time**. After those 16 safe completed single-ID results, return to four-way shared-auth batches. A second ambiguity or failed reauthentication stops rather than draining the queue. The CLI prints bounded category codes (e.g. `PROVIDER_WORKER_RESPONSE_TIMEOUT`, `LOCAL_BATCH_RESULT_VALIDATION`) and counts, never raw SDK messages or credentials. Default V30 behavior without `--adaptive-recovery` remains the original fail-on-first-ambiguity contract.

**Safe operator command after V33 merge:** no need to rerun V29, delete receipts or reinstall ThetaData.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
  if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main' }
  if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes exist' }
  git pull --ff-only origin main
  if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
  $py = '.\.venv\Scripts\python.exe'
  & $py -m pytest -q tests/test_options_native_spy_exact_exit_source_campaign_v30.py tests/test_thetadata_client.py
  if ($LASTEXITCODE -ne 0) { throw 'V33 tests failed' }
  & $py -m scripts.run_options_native_spy_exact_exit_recovery_v30 --plan data/research/spy_one_pair_exact_exit_demand_v29.json
  if ($LASTEXITCODE -ne 0) { throw 'V33 offline receipt preview failed' }
  & $py -m scripts.run_options_native_spy_exact_exit_recovery_v30 --plan data/research/spy_one_pair_exact_exit_demand_v29.json --run --adaptive-recovery --progress-every 25
  if ($LASTEXITCODE -ne 0) { throw 'V33 paid acquisition stopped; preserve full output' }
}
```

No historical transaction or fill is modeled. When V30 finishes or stops, run the V32 original+exact quote tape to measure exact selected CALL/PUT pair coverage; V32 must never run concurrently with V30 writing source receipts.
