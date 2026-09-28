

### 2026-09-28 — Same-run full-cohort stock/option dated source casebook (source-only)

The consolidated zero-GET workstation preflight now adds a fifth stage after targeted original C:-native raw daily CLOSE verification: an immutable D:-bound signed full-cohort source casebook. This is added to the same existing script, not a separate workstation command. It joins every original 14,902 signal / 29,804 case-right slots by immutable identities across the accepted quote reuse handoff, receipt-verified option timeline, frozen native-close demand and SHA-verified original native CLOSE source. Each selected slot retains its original OCC, quote-body SHA, observed later option bid/ask and provider update timestamp, and actual native raw stock CLOSE on exactly the corresponding ET session if present. Nonselected and missing-source slots remain in the denominator. It reports per-year counts for absent later two-sided option source, native exact daily gaps and dated stock+option source pairs; 2026 remains zero in this accepted 2021–2025 source population. Results are immutable under the configured D: options derived binding; source files and prior signed artifact fingerprints are not rewritten.

Dated source evidence **does not** prove matched stock/option observation timestamps: a provider update is not historical publication time, the original native daily bar does not carry a certified option-synchronous close timestamp, and original 09:35 entry cannot use later EOD. No deliverable/multiplier is inferred; no historical fill, Greek, option P&L, account return, PAPER/LIVE or new protected-holdout authority is granted. The source casebook is the bounded, receipt-linked join for subsequent independent clock/deliverable/cost validation and account replay, not a simulated trade. No new provider calls or broad original stock corpus scan are introduced. The fourth-stage native close reader remains 1–4 workers and stops on SHA/plan drift or an invalid required native source; exact missing daily bars remain explicit gaps.

One operator action after merge, from ATLAS PowerShell root:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_option_stock_eod_preflight_v1.py --native-workers 4; if ($LASTEXITCODE -ne 0) { throw 'Combined option-stock source preflight stopped; paste complete output. No blind paid retry.' } }
~~~

Next: inspect actual one-pass source counts and gaps before authorizing paid exact series; account-level simulation requires independent clock, original deliverable, commissions/fees, expiry and fill semantics, plus the accepted signed source population. Do not re-run earlier successful census/selection/acquisition stages merely for another status check.
