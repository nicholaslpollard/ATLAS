# Pre-Phase33 Alpha Gate — SEC XBRL Fundamental Quality / Accrual Mechanism

**Status: `ACCEPTED_NEGATIVE`. The source-only feasibility PASS, preserved PIT audit v1 FAIL, targeted v2 identity-repair PASS, frozen scientific contract, and development-negative closeout are complete. Protected returns remain unread and Phase33 remains blocked.**

## Purpose

ATLAS entered this gate with zero historically `SUPPORTED` modern alpha after valid negative Phases26–32. This gate tested a materially different information mechanism: point-in-time standardized quarterly fundamentals from original SEC 10-Q/10-K XBRL facts.

The economic family was fundamental profitability, cash-vs-accrual quality, and year-over-year fundamental change. It did not reuse Phase32 candidate labels, directions, 8-K event taxonomy, development performance, finalist choice, or protected result.

## Authoritative source

Official SEC `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` was the standardized-fact source through the accepted SEC EDGAR HTTP/fair-access seam. Official SEC submissions metadata supplied exact original filing/accession/date/acceptance chronology. Massive reference supplied PIT issuer-to-security identity after source-only entitlement/semantics validation.

## Source-only feasibility — accepted PASS

Contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Accepted target head:

`5a8c15f95417390d0d64ff240977adfb38a20c45`

Accepted evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

The deterministic source-only census used exactly 200 CIKs selected by SHA-256 ordering from the accepted Phase32 issuer inventory. Only issuer CIK discovery was reused; no Phase32 scientific/performance lineage was imported.

Accepted result:

- source inventory unique CIKs: **4,400**;
- sample: **200**;
- successful Company Facts documents: **200**;
- failures: **0**;
- accrual-history-ready issuers: **170**;
- profitability-history-ready issuers: **92**;
- group readiness counts: assets 174, cost of revenue 97, gross profit 78, net income 180, operating cash flow 180, revenue 136;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider reads/writes: **200 / 0**;
- broker/order/PAPER/LIVE/automation: **0**.

The feasibility PASS established source coverage only; it never established alpha.

## PIT source / chronology / identity audit — v1 preserved FAIL

Frozen audit contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Frozen audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

The audit used exactly 40 deterministic feasibility-ready issuers and up to 5 original 10-Q/10-K accessions per issuer. Company Facts supplied exact fact/accession association; official SEC submissions metadata supplied exact form/date/`acceptanceDateTime`; decision session was the first XNYS open strictly after acceptance; later accession versions never overwrote earlier facts.

The first target result was preserved as **`AUDIT_FAIL`**:

- successful Company Facts documents: 40;
- selected original filings: 200;
- SEC metadata reconciled: 198;
- acceptance decisions: 198;
- unambiguous PIT mappings: **139**;
- issuers with >=3 mappings: **28**, below frozen minimum 30;
- same-accession semantic conflicts: 0;
- protected return rows read: 0.

The failure was not bypassed or threshold-relaxed.

## Targeted identity-semantics repair — accepted PASS

Root-cause diagnosis showed the Massive historical identity query expanded the candidate universe with `active=false` and non-common-stock types, producing ambiguity from preferreds, warrants, units, rights, legacy tickers, and other non-target securities.

Targeted repair contract:

`alpha-gate-xbrl-pit-audit-v2-targeted-common-stock-active-only-identity-repair-no-market-outcomes`

Repair fingerprint:

`e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`

The owning-layer repair changed identity semantics to exact historical CIK/date plus `active=true` and `type=CS`, while preserving the same 40 issuers, accessions, SEC chronology, and numeric gates. The replay used existing local source-only caches and made zero provider calls.

Accepted v2 result: **`AUDIT_PASS`**.

- replayed identity decisions: 198;
- unambiguous PIT common-stock mappings: **171**;
- issuers with >=3 unambiguous mappings: **38**;
- same-accession semantic conflicts: 0;
- target/protected outcome reads: 0;
- provider calls/writes and trading authority: 0.

The v1 failure remains preserved evidence; v2 is the accepted corrected identity semantics.

## Frozen scientific contract

Scientific contract:

`alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Exactly six hypotheses were frozen before outcomes: gross-profitability improvement/deterioration, cash-profitability improvement/deterioration, and accrual-quality improvement/deterioration, with LONG/SHORT directions preregistered.

The contract froze PIT quarter reconstruction, year-over-year feature semantics, 63-session primary horizon, exact entry/exit chronology, SPY-relative and unhedged outcomes, direction-specific primary/stress costs, chronological selection/internal validation, a 63-session purge, dependence-aware bootstrap statistics, global `HOLM_BONFERRONI_GLOBAL_6`, robustness/concentration gates, one winner per direction, selection-only winner choice, no runner-up substitution, and finalist-only protected performance.

Development implementation fingerprint:

`3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

## Accepted development result

Accepted target head:

`58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`

Development status: **`ACCEPTED_NEGATIVE_DEVELOPMENT`**.

- predictor rows: **5,536**;
- development predictor rows: **4,157**;
- protected predictor rows: **1,379**;
- usable development outcomes: **3,963**;
- selection passers after every hard gate plus global Holm: **0**;
- selection winners: **0**;
- internal finalists: **0**;
- protected-return eligible finalists: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- Phase33 authority: **false**.

No candidate survived the frozen development screen. Therefore no internal finalist and no protected-performance read existed.

## Accepted negative closeout

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

Closeout result: **PASS / `ACCEPTED_NEGATIVE`**.

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Accepted artifact SHA-256 values:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

The closeout path performs zero provider calls and zero new market reads. It verifies only the persisted target evidence and proves protected returns remained unread.

## Final interpretation and authority

This exact XBRL fundamental-quality/accrual family is closed `ACCEPTED_NEGATIVE`. It may not be retuned after results by changing thresholds, costs, horizon, feature definitions, directions, multiplicity, issuer sample, or winner rules, and the protected holdout may not be opened to rescue it.

Historical supported modern alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. The master protected outcome window `2026-05-12..2026-08-11` remains unconsumed and is available only to a later scientifically valid, materially different preregistered mechanism.

See `docs/alpha_gate_sec_xbrl_pit_audit.md`, `docs/alpha_gate_sec_xbrl_pit_identity_repair.md`, `docs/alpha_gate_sec_xbrl_scientific_contract.md`, `docs/alpha_gate_sec_xbrl_development.md`, and `docs/alpha_gate_sec_xbrl_closeout.md`.
