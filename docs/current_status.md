# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-30 (America/New_York). Phase32 remains closed and merged `ACCEPTED_NEGATIVE`. The SEC XBRL fundamental-quality/accrual research program is also closed and merged `ACCEPTED_NEGATIVE`. The current pre-Phase33 mechanism is no longer at initial feasibility: beneficial-ownership source repair v2 passed, the finite Schedule 13D/13G scientific contract is frozen, and development acquisition is paused at a preserved pre-outcome transport failure after 3500/5200 source-only predictor items. Development stock/SPY returns remain unread, protected returns remain unread, the master holdout remains unconsumed, historical supported alpha remains 0, and Phase33 remains blocked.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md`, the retained beneficial-ownership source-repair/feasibility records, the accepted XBRL closeout records, `docs/phase32_closeout.md`, `docs/phase_flow.md`, and exact-head CI evidence before continuing.

## Authority state

- Accepted numbered foundation: through **Phase32**, merged into `main`.
- Phase32 remains closed `ACCEPTED_NEGATIVE`: frozen protected source-only evidence was **46 event rows / 33 signal sessions / 40 instruments**; the preregistered 50-row minimum failed before protected returns were opened, protected return rows read remained 0, and the holdout remained unconsumed.
- Phase26–32: scientifically valid `ACCEPTED_NEGATIVE`.
- Completed pre-Phase33 SEC XBRL mechanism: `ACCEPTED_NEGATIVE`, merged at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`, accepted closeout evidence fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`, with post-merge Ubuntu/Windows regression green.
- Current pre-Phase33 branch: `alpha-gate-sec-beneficial-ownership-scientific-contract`.
- Retained original source-feasibility mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.
- Current frozen scientific mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.
- Accepted historical modern alpha support: **0**.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- Master protected outcome window `2026-05-12..2026-08-11`: **unconsumed**.
- Development stock return rows read in current mechanism: **0**.
- Development SPY return rows read in current mechanism: **0**.
- Protected return rows read in current mechanism: **0**.
- Provider/broker/order/PAPER/LIVE/automation authority: **disabled**.
- Automatic broker failover: **disabled**.

Root cause before workaround remains mandatory. Failed research evidence must be preserved. No failed family may be rescued by changing thresholds, horizon, costs, features, direction, multiplicity, winner rules, or protected policy after results.

## Beneficial-ownership source lineage

Parent source-only feasibility contract:

`alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes`

Retained original source-feasibility mechanism identifier:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

Frozen parent feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

The original target source run failed before sampling/outcome reads and remains permanently preserved. Targeted source repair v2 corrected two owning-layer defects without weakening numeric gates: quarterly SEC `master.idx` responses were separated from complete-submission response sizing, and the official complete-submission header `SUBJECT COMPANY` CIK became authoritative security identity while master-index CIK remained provenance.

Targeted source-repair fingerprint:

`78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c`

Accepted v2 source result:

- quarterly SEC master indexes: **43/43**;
- complete submissions parsed: **200/200**;
- accession/form/date reconciliation: **200/200**;
- authoritative SEC-header `SUBJECT COMPANY` CIK extraction: **200/200**;
- unique authoritative subject CIKs: **195**;
- acceptance/decision sessions reconstructed: **200/200**;
- unambiguous PIT active common-stock mappings: **142**;
- market outcome reads: **0**;
- protected return reads: **0**.

This source result authorized only the later scientific freeze; it did not create alpha support or Phase33 authority.

## Frozen beneficial-ownership science

Current frozen scientific mechanism:

`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`

Scientific contract:

`alpha-gate-beneficial-ownership-scientific-v1-four-initial-ownership-intent-buckets`

Scientific fingerprint:

`4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`

Development implementation fingerprint:

`0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d`

Exactly four non-overlapping LONG hypotheses were frozen before any market outcome:

1. `initial_13d_5_to_10_long`;
2. `initial_13d_10_plus_long`;
3. `initial_13g_5_to_10_long`;
4. `initial_13g_10_plus_long`.

Only initial Schedule 13D/13G filings are performance eligible. Filing-level ownership percentage is the maximum valid cover-page percent-of-class across reporting persons, never a sum. Entry is the first XNYS open strictly after SEC acceptance; primary exit is 63 XNYS sessions later. Primary performance is stock open-to-63-close minus same-window SPY minus 10 bps LONG cost, with positive after-cost unhedged return independently required. Stress cost is 25 bps. Development is chronological 70/30 with a 63-session purge; dependence-aware block bootstrap and global `HOLM_BONFERRONI_GLOBAL_4` are frozen. At most one selection winner may proceed to internal confirmation; runner-up substitution is forbidden. Protected returns are finalist-only.

The detailed sample sizes, chronology, minimum counts, fold rules, concentration controls, confidence thresholds, diagnostics, and protected boundary are normative in `docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md` and must not be changed after outcome access.

## Preserved pre-outcome development transport failure

The target development runner reached:

`3500/5200` source-only predictor items

and stopped because one legitimate official SEC complete-submission archive exceeded the historical/default **20,000,000-byte** submission ceiling. The failure occurred before the runner emitted:

`Source-only predictor reconstruction: PASS`

Therefore:

- development stock return rows read = **0**;
- development SPY return rows read = **0**;
- protected return rows read = **0**;
- protected holdout consumed = **false**;
- scientific selection evidence read = **none**.

The existing source cache through approximately 3500 items is valid acquisition evidence and **must be retained**.

Frozen development transport-repair fingerprint:

`a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb`

Transport policy remains:

- quarterly master indexes: **64,000,000 bytes**;
- historical/default complete submissions: **20,000,000 bytes**;
- scientific complete-submission ceiling: explicit opt-in, bounded at **256,000,000 bytes**;
- SEC archive pacing: **5 calls/second**, **0.2-second minimum interval**.

The scientific runner explicitly opts into the 256 MB ceiling; unrelated/default consumers remain at 20 MB. No scientific fingerprint, sample, hypothesis, threshold, cost, horizon, split, bootstrap, multiplicity, robustness, winner/finalist, or protected rule changed.

## Repository repair and certification state

The backward-compatibility defect discovered by CI was that `_response_limit(url)` had become instance-only. Historical source-repair tests and the accepted source transport contract require the static seam.

Compatibility repair code commit:

`8b4a5dc8dc8931062cd34ec30b71b38f82a53a9d`

The repaired provider now:

1. retains static historical `_response_limit(url)` = 64 MB index / 20 MB submission;
2. retains `_configured_response_limit(url)` for the explicit per-client scientific submission override;
3. begins request sizing through the accepted historical response-limit seam;
4. applies a configured override only when the client was explicitly constructed with a non-default submission ceiling;
5. leaves index sizing at 64 MB even for the scientific client.

Focused beneficial-ownership validators and unit tests pass on **Ubuntu and Windows** at that code commit. The documentation synchronization commit must also receive exact-head focused and full Ubuntu/Windows certification before target execution.

## Immediate next action

1. Finish exact-head repository certification after this status/roadmap/README synchronization.
2. If exact-head focused and full ATLAS CI are green on Ubuntu and Windows, update the target machine to that exact branch head without deleting any beneficial-ownership cache.
3. Resume `scripts/run_alpha_gate_beneficial_ownership_development.py`.
4. The runner must first complete source-only predictor reconstruction and emit `Source-only predictor reconstruction: PASS`.
5. Only after that PASS may the already-frozen development study open development stock/SPY outcomes.
6. Protected returns remain sealed unless one fixed finalist later satisfies all frozen development and protected source-only precheck requirements.

Do **not** start another alpha mechanism, alter science, delete cache, or manually bypass the source-only reconstruction boundary.

## Retained accepted-negative provenance

- Phase31 SEC Form-4 insider-transaction alpha: `ACCEPTED_NEGATIVE`, merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 SEC 8-K material-event alpha: `ACCEPTED_NEGATIVE`, merge `69f8aa81289934b71f2652482c747391917c15a3`; protected source-only evidence **46 rows / 33 sessions / 40 instruments**, protected return rows 0, holdout unconsumed.
- Pre-Phase33 SEC XBRL fundamental-quality/accrual alpha: `ACCEPTED_NEGATIVE`, merge `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`, accepted closeout evidence fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.

All retained negative families remain closed to post-result rescue. Their protected outcome reads remained zero under their accepted closeouts.

## Downstream boundary

Phase33 is still blocked because accepted historical `SUPPORTED` alpha remains zero. The roadmap remains conditional rather than schedule-driven. LIVE, automatic broker failover, and any new trading authority remain unavailable until their later separately accepted gates.
