# Phase 31 — Independent Negative Closeout

**Disposition:** `ACCEPTED_NEGATIVE`

**Target-machine closeout date:** 2026-08-28

**Accepted closeout implementation head:** `92e61b74d3c6cf95db122b1981ed2b53ab1c7b07`

**Frozen scientific policy fingerprint:** `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

## Plain-English result

Phase31 tested whether public SEC Form-4 insider purchases and sales provided robust, tradable future-return information under the frozen ATLAS research standard. The development study executed successfully, but none of the four preregistered hypotheses survived selection. The independent closeout then reconstructed the decisive sample evidence without importing the development implementation and proved that every candidate failed a mandatory frozen selection gate.

Phase31 therefore closes as a valid negative research result. It grants no alpha authority and does not unlock signal-to-trade construction.

## Development result preserved

The target-machine development run read 5,400 frozen development predictor rows and produced 5,371 usable outcome rows after exact path controls:

- missing exact stock path: **4**
- focal-stock split crossing: **25**
- protected candidate rows read: **0**
- protected returns read: **0**
- protected holdout consumed: **False**.

Selection results under the frozen 750-row / 250-session / 250-unique-ticker minimum and the remaining profitability, robustness, concentration, bootstrap, and global-Holm requirements were:

| Candidate | Rows | Sessions | Unique tickers | Development disposition |
| --- | ---: | ---: | ---: | --- |
| `open_market_purchase_long` | 1,516 | 641 | 230 | FAIL |
| `clustered_open_market_purchase_long` | 638 | 376 | 136 | FAIL |
| `open_market_sale_short` | 2,355 | 785 | 216 | FAIL |
| `clustered_open_market_sale_short` | 1,281 | 645 | 131 | FAIL |

The development runner produced:

- selection survivors: **0**
- selection winners: **0**
- internal-validation candidates: **0**
- frozen finalists: **0**.

Two candidates had positive-looking development diagnostics: `clustered_open_market_purchase_long` had a positive selection LCB and `open_market_sale_short` had a positive selection LCB. Those observations do not change the result. Both violated mandatory preregistered sample/concentration requirements, neither survived the global four-hypothesis Holm family, and post-result rescue or runner-up substitution is forbidden.

## Independent negative reconstruction

Runner: `scripts/run_phase31_closeout.py`

Independent result:

`PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`

The independent path reconstructed the exact frozen development predictor population and exact decision-open to t+20-close path census:

- development predictor rows: **5,400**
- usable outcome rows: **5,371**
- missing exact stock path: **4**
- split crossing: **25**.

It independently reconstructed the selection sample counts shown above and proved that **all four candidates fail the frozen 250-unique-ticker minimum**; the clustered purchase candidate additionally fails the 750-row minimum. Therefore no candidate can legally be a selection survivor irrespective of favorable return diagnostics.

This proof is intentionally simpler than reusing the development bootstrap/Holm machinery and is independent of `phase31_development.py`.

## Final authority state

- selection survivors: **0**
- selection winners: **0**
- frozen finalists: **0**
- supported candidates: **0**
- Phase31 disposition: **`ACCEPTED_NEGATIVE`**
- Phase32 signal-to-trade entry satisfied: **False**
- protected candidate rows read: **0**
- protected return rows read: **0**
- protected holdout consumed: **False**
- provider reads/writes: **0 / 0**
- broker reads/writes: **0 / 0**
- orders / PAPER / LIVE: **0 / 0 / 0**.

The master protected outcome window `2026-05-12..2026-08-11` remains outcome-unopened and reusable for a future materially distinct alpha family under a newly frozen contract.

## Anti-workaround conclusion

`docs/phase31_end_to_end_anti_workaround_audit.md` is `PASS`. The closeout preserves the original feasibility failure, chronology/source-quality repairs, frozen policy, predictor membership, development evidence, zero protected-return reads, and no-runner-up/no-retuning rules.

No Form-4 threshold, role filter, transaction-value filter, cluster definition, horizon, cost, multiplicity rule, or sample gate may now be changed to reinterpret Phase31 as positive.

## Next project action

Phase31 should be merged as `ACCEPTED_NEGATIVE`. Because no accepted alpha exists, the previous Phase32 signal-to-trade entry condition is not satisfied. The roadmap must therefore be rebaselined to another materially distinct alpha information source before downstream trade construction can begin.
