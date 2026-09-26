# ATLAS 2025 Exact Historical Contract Reference Dossiers V1 — 2026-09-26

## Distinct development stage after accepted CALL shortlist

Input is the already written PIT CALL shortlist `e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268`. The original source pilot and 11+1 closeout are complete and must not run again. Eleven actual provisional OCC CALL symbols (AGIO, AMGN, ATRC, BANF, DAKT, ISRG, LNT, OLLI, SRRK, TEM, TSLA) are frozen for a *new* independent historical reference source. FSLY remains the original exact-query source gap and receives no request. An OCC-format chain row by itself does not establish historical standard delivery.

Frozen per-contract query: `GET /v3/reference/options/contracts/O%3A{OCC}?as_of={previous_session_chain_snapshot_date}` against the configured Massive HTTPS origin. Do not replace 2025 terms with a present-day overview. Each SHA-bound request specifies one symbol, snapshot/as-of, underlying, CALL side, strike, expiry and the source-chain SHA. A reference row must agree exactly on those identity fields; inspect `shares_per_contract`, `exercise_style`, `additional_underlyings` and `cfi` only as reference evidence. A matching 100-share/US-American style row with no reported additional underlyings is *structurally consistent, deliverable still unverified*; non-100 terms, extra underlying, absent fields or conflict remain separate review states. No fetched reference row alone independently certifies historical adjusted/OCC deliverables.

Massive's contracts overview and options contract endpoints expose the reference attributes above. The separate V7 bulk corpus contains known current/historical reference/deliverable disagreements and remains independently paused; the targeted 11-symbol stage neither resumes nor consumes it. Sources: https://massive.com/docs/rest/options and `docs/research/historical_option_reference_v6_artc_deliverable_cfi_conflict_20260922.md`.

## Bounded requests, no replay, retention

Offline preview is the default and spends zero requests. An explicit authorized execution may start at most 11 NEW exact reference requests, single worker, at least 13 seconds between starts to respect the previously observed 5/min Massive reference throttle. Do not run another Massive reference job concurrently. Every request creates an exclusive fsynced attempt marker **before transport**. Every received response, including HTTP failures, is stored with original raw bytes and a separately fingerprinted classification receipt. Non-200, malformed, conflicting or transport failure stops the job. An incomplete prior attempt or quarantine *always blocks* automatic replay. Fully verified original completed receipts are reused. Raw bodies and attempt markers are never deleted or overwritten. The reference cache and exact plan are new private D:-bound files; no provider credentials or raw user data go to GitHub.

Operator gate once the code is merged, with Massive API token already configured:

~~~powershell
.\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_exact_reference_v1.py --authorize-reference-reads --confirm-development-reference-only --max-new-requests 11
~~~

Zero-network preview omits all flags. The authorized run prints only the frozen request identities and safe classifications; it does not print provider raw response bodies, secrets or sensitive headers. A failure leaves its exact original raw/attempt/receipt for review; do not retry acquisition blindly. The provider's reference subscription/billing cannot be inferred from GET count, and the separate MarketData credits reported earlier are not consumed by this Massive endpoint.

## Authority boundary

Output is a new historical *reference dossier* only. Even if all 11 references are structurally consistent, historical deliverable/adjustment certification and point-in-time contract availability remain subject to independent evidence and quarantine rules. No MarketData selected-contract quote series, executable entry/fill, option P&L, strategy promotion, PAPER, LIVE or broker authority. The next stage is a separately scoped historical quote/cost feasibility plan after inspecting the actual reference outcomes.

**2026-09-26 PR #238 merge acceptance:** All ten GitHub checks passed, including full Linux and Windows suites (2,609 tests plus four subtests on each). Exact PIT reference dossiers were squash-merged at `438b3df794f1b382dbee54bb396e3d1fbffbc336`. Operator's accepted prior CALL shortlist remains fingerprint `e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268`. The new next workstation gate is a *single new, explicitly authorized* eleven-symbol historical reference acquisition, not another source/closeout/shortlist verification; the CLI first binds and prints the exact local new plan, then starts at most eleven new Massive GETs, one worker, >=13 seconds between starts, preserving raw/receipts/attempts and stopping on any quarantine. It prints HTTP status and safe structural terms on completion. No original MarketData pilot requests are repeated, and no execution-price/P&L authority follows.
