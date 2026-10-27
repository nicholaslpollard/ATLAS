# V29 — One preselected weekly SPY option pair + exact missing exit-contract source demand

## Trigger: successful V28 workstation run

V26–V28 targeted regressions: **18 passed in 2.36s**. The zero-provider original-source V28 audit reconciled **4,862** qualified candidate CALL/PUT entry pairs at each of five exit-review holding periods. At +5 sessions: **780 exact pairs observed, 3,999 both rights absent from retained response, 83 other quote quality/skew failures, no missing source responses**. Across the five review periods, **33,522 distinct dated contract rights** were absent from the retained `strike_range=2` surface responses. These are *retained response absences*, NOT provider or market no-data confirmations.

V27 conditional 10:00 ask-to-bid mean option premium returns were -3.53% to -12.10% across 1–5 sessions. The 4,862-pair original cohort is **not the frozen SPY one-pair ATM straddle trading strategy**. We must not download 33,522 contract rights to retrospectively optimize all candidate strikes, confuse observability-conditioned quotes with trades, or mistake the source-completeness problem for an SDK max-DTE defect.

## Implemented V29 transition: from 4,862 candidates to ONE physical-price-selected pair per week

The existing accepted-native SPY minute reader `review_spy_development_minute_coverage` already verifies the original 2018–2025 stock source lineage, 411 predeclared weekly decision dates, prior 21 closing-minute clocks and the exact pre-decision **09:59–10:00 SPY raw stock-minute close** for each eligible week, with bounded per-month memory and no new provider calls. The bar end is a historical observation clock; **its genuine availability by the 10:01 order cutoff is unproved**. The corporate-action return adjustment and option IV/OI/rate/dividend inputs also remain unproved. V29 must never represent this physical stock observation as PIT-qualified or sufficient to authorize historical fills.

V29 performs the frozen pair identity procedure using **entry-time** evidence only:

1. Enumerate original V12/V14-indexed 10:00 SPY quote *identities* within 30–45 calendar DTE. Extra over-DTE original rows stay preserved and ignored for selection.
2. Select the **earliest expiry** in the band, even if it has no executable quoted pair. If there is no common CALL+PUT strike for that expiry, abstain (do not choose a later expiry).
3. From that expiry's common CALL+PUT strikes choose the one closest to the physically observed SPY 09:59 minute close; resolve exact midpoint ties in favor of the **lower strike**.
4. **Only after fixing the identity**, apply existing V26 bid/ask, displayed-size, <=30-second quote-age, <=15% per-leg spread and <=1-second pair-clock screening. Failed selected quotes force abstention; no hindsight/liquidity fallback to another strike.
5. For each selected pair, examine the frozen five subsequent XNYS-session **10:00** review source responses and identify the exact same originally selected expiry/strike CALL/PUT rights. Qualifying review quotes are retained as observations only, never fills. If an original response is present but the original contract right is **absent**, add an individual exact-contract/date request to the bounded deduplicated future acquisition **PREVIEW**. If the original right is already present but quote quality fails, do not re-request it merely to hide the failure. If the entire original review source is unavailable, retain that state separately.
6. Deduplicate exact missing source demand and keep at most 411×5×2 = 4,110 distinct right requests (typically fewer). **No GET occurs in V29.** A query ID is a local fingerprint, not a source permission, provider response or assumption of later outcome/contract availability.

The core is `packages/data/options_native_spy_physical_spot_exact_demand_v29.py`, executed via `scripts/run_options_native_spy_physical_spot_exact_demand_v29.py`. The source reader is V26's SHA-confirmed original archive/receipt entry and exit adapter, with the same bounded 48-source LRU cache. V29 registers its research observation before opening historical option exit prices in the append-only trial ledger. `--output` writes a **new derived preview JSON** only; no source archive is changed.

## Operator action after CI/merge

One PowerShell block:

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
  if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS not on main' }
  if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
  git pull --ff-only origin main
  if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
  $py = '.\.venv\Scripts\python.exe'
  & $py -m pytest -q tests/test_options_native_spy_physical_spot_exact_demand_v29.py tests/test_options_native_exit_coverage_attribution_v28.py
  if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
  & $py -m scripts.run_options_native_spy_physical_spot_exact_demand_v29 --output data/research/spy_one_pair_exact_exit_demand_v29.json
  if ($LASTEXITCODE -ne 0) { throw 'Historical source selection plan failed' }
}
```

The command scans up to 125 historically accepted monthly SPY minute units **once**, streams 411 original weekly quote entry sources and their five associated review sources, and prepares one result showing:

- Number of frozen weeks with physically observed stock spot; valid earliest-expiry/nearest-spot pair identity; quote-quality abstention count; no retrospective late contract selection.
- Number of source response-missing exact original CALL/PUT rights actually relevant to those selected one-pair-per-week pilot entries, broken down by session/year. This replaces the enormous V28 all-strikes candidate gap count with focused request demand.
- One preview record per absent exact option right (date/clock/expiry/strike/right plus immutable source query linkage) to feed the subsequent guarded provider campaign if appropriate.

If the report filename already exists, choose a different path; outputs never overwrite.

## Next development step, immediately after preview

Build/run a paid-source **resumable exact-contract recovery campaign**, using ATLAS's already present `option_at_time_quote(symbol, date_et, time_of_day_et, expiration, strike, right)` SDK wrapper. The limited demand and immutable started/terminal receipts must be committed before sending requests, with original raw/normalized provenance and no ambiguous same-query retries. Recover missing quotes for selected entries only—**not all 33,522 V28 rights**—while the Standard membership remains active. Confirm separately that exact contract requests bypass the broad `strike_range=2` response geometry and do not invent 10:01 fills.

In parallel, bind original source 09:59 SPY spot availability, PIT economic close returns/actions, prior OI, IV, rates, dividends, accepted standard OCC multiplier/deliverable and option hours. Freeze the strategy volatility signal. After exact review quote recovery, use a separately typed historical-modeled 10:01 execution timeline with explicit latency/spread/fee assumptions, unknown unfilled/expired/settled positions, and a chronological account; only then benchmark weekly/monthly/annual drawdown and run parameter sweeps or combined strategies. Existing all-pair quote metrics remain **exploratory**, never accepted strategy alpha; 2026 protected holdout remains consumed.

**No options trading or historical fill authority is granted by V29**, and source-present-at-10:00 does not imply executable at 10:01.
