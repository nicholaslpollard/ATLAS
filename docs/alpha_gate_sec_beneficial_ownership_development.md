# Pre-Phase33 SEC Schedule 13D/13G Beneficial Ownership — Development Result

**Development disposition: `ACCEPTED_NEGATIVE_DEVELOPMENT`. The source-only predictor reconstruction passed before outcomes opened. Protected returns were never opened, the protected holdout remains unconsumed, historical supported alpha remains 0, and Phase33 remains blocked.**

## Frozen lineage

Scientific mechanism:

`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`

Scientific contract:

`alpha-gate-beneficial-ownership-scientific-v1-four-initial-ownership-intent-buckets`

Scientific fingerprint:

`4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`

Development implementation fingerprint:

`0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d`

Development transport-repair fingerprint:

`a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb`

Accepted development target head:

`067dc13429c22dc4e789959f56644423f0947946`

Accepted closeout evidence fingerprint:

`c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`

## Preserved pre-outcome transport failure

The earlier target run stopped after roughly **3500/5200** source-only predictor items because one legitimate official SEC complete submission exceeded the historical/default 20 MB archive ceiling. That run stopped before `Source-only predictor reconstruction: PASS`, with development stock/SPY return rows read = 0 and protected return rows read = 0. The cache was retained rather than deleted.

The narrow transport repair left the frozen science unchanged, retained the historical/default 20 MB complete-submission ceiling and 64 MB quarterly-index ceiling, and allowed only the scientific client to opt explicitly into a bounded 256 MB complete-submission ceiling.

## Accepted source-only predictor reconstruction

The repaired target run completed the source-only stage first and emitted `Source-only predictor reconstruction: PASS` before any development outcomes opened.

- predictor rows: **3,652**;
- development predictor rows: **2,763**;
- protected predictor rows: **889**;
- candidate counts: 938 initial 13D 10%+, 742 initial 13D 5–10%, 272 initial 13G 10%+, and 1,700 initial 13G 5–10%;
- provider source reads: **3,133**;
- target outcome rows read before development opened: **0**;
- protected return rows read at predictor completion: **0**.

The predictor diagnostics remained fail-closed for ambiguous or unavailable PIT common-stock identity, boundary censoring, out-of-bin ownership percentages, and unparsed ownership percentages.

## Accepted development evaluation

After the source-only PASS, the runner opened development-only exact entry/exit paths for the **2,763** development predictor rows under the already-frozen 63-session stock/SPY-relative contract.

- development outcomes read / usable rows: **2,412**;
- exact stock path missing rows: **306**;
- split-crossing censored rows: **46**;
- selection window: `2021-08-16..2023-12-26`;
- 63-session purge: `2023-12-27..2024-03-27`;
- internal window: `2024-03-28..2024-12-31`;
- development sessions: **850**;
- selection sessions: **595**;
- internal sessions: **192**.

Selection passers: **0**.

Selection winners: **0**.

Internal finalists: **0**.

Protected-return eligible finalists: **0**.

Protected return rows read: **0**.

Protected holdout consumed: **false**.

Phase33 authority: **false**.

Because no hypothesis survived the frozen development hard gates plus global Holm–Bonferroni correction, no candidate was eligible for internal confirmation or protected performance. Runner-up substitution remained forbidden.

## Scientific interpretation

The exact preregistered initial Schedule 13D/13G ownership-intent/concentration family did not earn ATLAS support. This is a valid negative result, not an implementation failure. Regulatory-era diagnostics remain descriptive only and cannot be used to redefine the hypotheses after observing performance.

The protected holdout was not spent to inspect a family that had already failed development. The resulting negative disposition is eligible for immutable closeout using only the persisted artifacts and their exact hashes.
