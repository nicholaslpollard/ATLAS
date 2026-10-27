# V26 — Frozen 411-week SPY original quote-pair matching and fee sensitivity

**2026-10-27 acquisition evidence:** The V24 operator run performed all 1,104 remaining frozen 10:00 SPY exit requests in one authenticated shared SDK session. It archived 1,103 original bodies (1,102 out-DTE, 1 invalid), recorded one explicit no-data response and **no new provider failures**. The complete 1,570 exit-source state inventory is: 1,558 over-DTE original archives, three invalid-schema originals, eight pre-existing no-source errors, one explicit no-data; unattempted=0. Entry sources are the separate 411-week set. No simulator or protected return was opened.

This closes the **acquisition** queue, not the historical execution/scientific qualification gates. The original over-DTE condition means the provider's source response contains extra expiries; valid quoted in-range observations may be inspected with original SHA and per-row identity intact. The three schema-invalid sources and earlier eight failed dates remain excluded from paired research, **not silently accepted or re-requested**.

## New, additive, offline V26 diagnostic

`packages/data/options_native_original_pair_diagnostic_v26.py` and
`scripts/run_options_native_original_pair_diagnostic_v26.py` perform a single
read-only pass over the original 411 weekly entry requests and their five
post-entry 10:00 review requests. It uses the existing V12 receipt+V14 index
source-linked entry reader (410 archive identities), and the SHA/gzip/terminal
receipt-verified V19 exit archive reader. The separately stored 2025-06-09
entry remains unavailable to this adapter until it has independently
qualified lineage; no substitution is authorized.

The experiment takes **all** original CALL+PUT same-expiry/strike candidates
at the frozen entry surface with 30–45 calendar DTE, both two-sided,
displayed bid/ask sizes, <=30-second age, <=15% per-leg spread and <=1-second
inter-leg quote-time skew. It does NOT choose one ATM pair, choose a trade,
or inspect future availability before enumerating entry candidates. At each
of five predetermined later review dates it matches **the exact original
contract pair** and repeats quote-quality screens. An originally 30–45 DTE
option may now have under 30 DTE; exit scanning permits 0–45 DTE and
never replaces the expired or missing contract.

For all observed entry/exit pair matches the module computes a **hypothetical**
observed 10:00 entry ASK sum to subsequent 10:00 review BID sum premium
percentage change. Assumed two-leg commissions per contract per side
are swept at $0.00, $0.65 and $1.30, with four leg-side charges per round trip.
Only matched quote **observations** populate the numeric diagnostics;
all unmatched entry pairs and all unresolved sources remain in the full
entry and review denominators. Reports by-entry-year and matching-review
counts, per-fee mean/median/positive fraction, source-state losses and
total original pair candidates.

**Results are NOT causal strategy returns, historical executions, a
complete capital account or proof of profitability.** Missing later
quotes create survivorship/coverage conditioning of the paired subset.
The 10:00 option snapshot is not a verified 10:01 fill, and PIT spot,
eligible ATM selection, previous OI, American IV, rates, issuer actions,
spread/latency behavior, exercise settlement and terminal account marks
are not present. Do not rank option strategies or select risk
thresholds from the observed matched subset as though independent.

## Next workstation command after CI and merge

From the ATLAS repository root, after `git pull --ff-only origin main`, run
the **read-only** full frozen source-to-source diagnostic. It makes **zero**
ThetaData or broker requests and does not change any original archives:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_options_native_original_pair_diagnostic_v26.py tests/test_strategy_sweep_fastlane_v1.py
.\.venv\Scripts\python.exe -m scripts.run_options_native_original_pair_diagnostic_v26 --output data/research/spy_pair_diagnostic_v26.json
```

The output path in the second command should be entered as
`data/research/spy_pair_diagnostic_v26.json` (no whitespace); choose a new
filename if that report already exists. This is a newly written derived
diagnostic only. Use the default console mode to avoid any write.

## Forward to real simulation

1. **Inspect this actual paired original-source coverage**. If too many entry-time
   pair candidates lack quality exit observations, identify whether the cause
   is changing strike-range, explicit no-data/errors, market illiquidity, or
   uncovered exact timestamps; diagnose rather than backfill from future.
2. Build a separately typed **historical execution-admission adapter**, not a
   shortcut setting the synthetic fixture-origin flags. Independently bind
   PIT 09:59–10:01 underlying spot, previous 20 economic returns, corporate
   actions, rates, previous OI and American-model IV; freeze ATM/expiration
   selection using those entry-time inputs only. Preserve original quote
   observed time vs historical available time and 10:01 order eligibility.
3. Evaluate the frozen SPY straddle's five-date management rule with confirmed
   later exact selected contracts and explicit unknown/unfilled states.
   Account-level cash, equity and drawdown must be chronologically marked;
   any unknown terminal mark is reported NULL, not manufactured.
4. Integrate the historical event tape with PR #392's scenario-sweep
   orchestration; then add the genuine mixed stock/options shared-capital
   engine. Record every tested variant and require independent forward
   validation before claiming alpha.
