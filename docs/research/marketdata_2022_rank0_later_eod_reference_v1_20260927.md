# Frozen 2022 rank-zero CALL later-EOD bid/ask reference paths V1 — 2026-09-27

## Accepted input, no reacquisition

The original full 2022 PIT-frozen monthly CALL source acquisition and local evidence audit are accepted, not candidates for rerunning: 6,398 complete exact OCC EOD histories, 473,683 observations, zero quote gaps/pending; read-only original audit \`f1adec38fbffa2fa2612dda0e3f68cac128c39434cc99651b6a30cddcd8b5298\` bound to immutable plan \`017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786\`. D: raw quote responses total 73,016,761 bytes. The new **accepted operator result** for rank-zero readiness: \`8f561664c6ee0bc11aed44bfe4a84606701e93a9aa8a3cbd7f4b53a102452efc\`; 2,643 original representative opportunity memberships, 2,227 deduplicated original preferred CALL histories, zero opportunities without later EOD observations, 5 without later two-sided context, 2,638 with later two-sided context and 2,629 with two or more later two-sided dates. 2,435 have a later positive-reported-volume observation. Previous source report and raw/receipt files remain immutable. This readiness is NOT a simulator fill/P&L result.

**C: alias and physical D: storage.** \`AtlasSettings.resolved_path("data/options/…")\` deliberately preserves the stable project-relative C: string, then asserts \`data/options\` refers to the same filesystem directory as \`D:\ATLAS_DATA\options\` through the configured junction. Thus the prior manifest printed \`C:\Users\cyberdyne\Desktop\ATLAS\data\options\manifests\…\` even though the *physical* storage is D:. This new CLI prints both the logical namespace and physical D: derived output path explicitly; never create an independent second options data store on C:.

## New and different result: retrospective EOD reference path, not original 09:35 trade

\`scripts/build_marketdata_2022_rank0_later_eod_reference_v1.py\` consumes the accepted immutable rank-zero readiness manifest, the same 6,398-item plan and **only the 2,227 original preferred CALL quote bodies/receipts needed to derive reference values**; original SHA/body/receipt verification is needed to compute NEW price fields, not a repeat of the whole-corpus audit. It makes **zero provider GETs**, uses no protected stock-outcome labels, and never changes original data.

Pre-registered rules, applying to ALL 2,643 structurally chosen representatives:
1. Keep the original rank-zero CALL choice exactly as of prior-session historical chain/source evidence; no future-informed fallback to a more liquid strike.
2. Exclude the entire original stock decision date (09:35 ET decision), so *same-day EOD is never used as a morning entry*.
3. Find the first later-date recorded EOD-source row with **both bid and ask strictly positive and ask ≥ bid**, then the next **strictly later dated** qualifying observed row for that same OCC symbol. Record provider original \`updated\` UTC time, dates, spread references and whether each reported volume is positive. Do not infer every row was observed precisely at 16:00 ET; no quote age or executability authority.
4. Emit a *hypothetical per-share reference* of (subsequent observed bid − first observed ask) and its fraction of the first ask; round decimals deterministically to six places. It is a price-reference calculation, **not** cash/realized option P&L, an observed fill, an independently verified standard 100-share contract, a stock-strategy comparison, or an investable result.
5. Include the original full structural denominator and explicit absence statuses when the contract has zero or only one later valid two-sided row. No return is imputed for an unavailable mark, and no survivor-biased claim for the full set. Report count with a valid path, positive reported volume at each reference, calendar time between observed rows, and the descriptive median reference fraction *among available pairs only*.

The expected readiness census gives a source-data bound of 5 no later two-sided reference, 9 entry-only (2,638 − 2,629), and 2,629 first-plus-next later observations, subject to newly verified source/receipt identity and timestamp reconciliation. This numerical accounting is source availability ONLY. No adjusted deliverables, contract economics or original 09:35 option quote snapshots are established. The actual observed reference median has not yet been computed/accepted until the operator runs this stage.

Output is a small **new immutable derived** JSON on D: under \`data/options/derived/marketdata_2022_rank0_later_eod_reference_v1_<readiness-prefix>.json\`. It is not a duplicate raw corpus, does not overwrite previous source or receipt, and is reused only if byte-equivalent. Progress prints every 250 distinct rank-zero histories. The CLI explicitly prints the actual physical external storage path.

## Next distinct operator handoff after green merge

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\\.venv\\Scripts\\python.exe scripts\\build_marketdata_2022_rank0_later_eod_reference_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Later-EOD price-reference gate stopped. Preserve original local evidence and full output; no paid retry.' } }
\`\`\`

After the operator submits results, decide whether to implement a **separately preregistered EOD-entry reference scenario** and what true intraday 09:35 options data/deliverable evidence must be acquired to support the user's actual morning-stock-vs-option backtest. Supported 2023–25 year-specific sources and other expirations remain separate planned acquisition work. Do not optimize exit/strike rules on holdout or silently generalize these 2022 EOD observations to 2025/2026.
