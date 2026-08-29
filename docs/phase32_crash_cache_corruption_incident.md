# Phase32 Crash-Cache Corruption Incident

Status: **ACTIVE REPAIR / NO MARKET OUTCOMES OPENED**

## Incident

During the resumable Phase32 full-history predictor/source acquisition, the target Windows machine suffered an abrupt system crash while unrelated software was being installed. After restart, the Phase32 acquisition resumed from existing atomic caches and later stopped at 19,965 / 36,309 filing entities with:

`Expecting value: line 1 column 1 (char 0)`

Progression stopped immediately. Development returns remained unopened.

## Read-only diagnosis

A full local parse scan covered:

- 73,292 JSON files;
- 20,278 JSONL files;
- 754,868 JSONL rows.

Exactly two JSON cache files were malformed; every JSONL cache parsed successfully and no stale sibling temporary files were present.

1. `massive_reference/2026-06-23/34243222535982df996fa4a7.json`
   - size: 601 bytes
   - SHA-256: `1b94bb6a330c915941eaa7d5b7a1d84a7d7832e3a0e3f20a03cc23925242aa2b`
   - null bytes: 601
   - unique byte values: 1

2. `sec_submissions/0002131853/0001213900-26-068397.json`
   - size: 743 bytes
   - SHA-256: `8d61db14747e1bfe393ddf9f98e7120b001e2dbc28b5d25b7db6a0603d22f176`
   - null bytes: 743
   - unique byte values: 1

Both files retained their expected nonzero lengths but consisted entirely of zero bytes. This pattern is compatible with abrupt system-crash/write-back loss of reconstructible cache contents. ATLAS atomic writes guarantee atomic visibility but do not request `fsync` by default for reconstructible caches, so an operating-system crash can still leave a final cache pathname whose storage contents were not durably committed.

No evidence supports a provider semantic defect, identity defect, hypothesis defect, or market-outcome defect.

## Repair contract

Repair script:

`scripts/repair_phase32_crash_corrupted_cache.py`

Contract:

`phase32-crash-corrupted-cache-targeted-quarantine-v1`

The repair is deliberately narrow:

- only the two diagnosed paths are eligible;
- exact byte length, SHA-256, and all-null payload are required before mutation;
- any mismatch fails closed;
- exact corrupt bytes are preserved under `quarantine/phase32-cache-crash-20260829/` as `.corrupt.bin` evidence;
- the original two cache paths are removed only after the diagnosed payload is matched/preserved;
- a durable JSON manifest records the repair;
- the normal Phase32 acquisition path must then reacquire only those missing authoritative source records;
- all other existing caches remain untouched and reusable.

## Scientific boundary

This incident and repair do **not** change:

- frozen Phase32 policy fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
- hypotheses;
- chronology;
- costs;
- sample/concentration gates;
- multiplicity controls;
- identity-v4 rules;
- protected-evidence boundary.

Stock, SPY, options, development-return, and protected-return rows remain unread. Broker reads/writes, orders, PAPER, and LIVE remain zero/disabled.

After the targeted quarantine repair, rerun the cache-integrity diagnostic. Only if the cache parse surface passes should the normal source-only acquisition resume. Its existing resumable caches remain authoritative subject to the normal source/identity validators.
