from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

README = ROOT / "README.md"
ROADMAP = ROOT / "docs/roadmap.md"
EVIDENCE = ROOT / "docs/evidence/b35_source_only_preflight_acceptance.json"
WORKFLOW = ROOT / ".github/workflows/_b35_source_preflight_publish.yml"
SELF = ROOT / "scripts/_publish_b35_source_preflight.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


readme_old = '''- **The B35 finite-replay implementation package has opened no B35 historical outcomes.** For this package, consumed-master rows read = `0`, future-blind rows read = `0`, provider calls = `0`, broker reads = `0`, broker writes = `0`, PAPER orders = `0`, LIVE operations = `0`; strategy promotion = `false`, selector promotion = `false`, PAPER authority is unchanged/absent, and LIVE authority remains `false`. The governed finite replay scope is fixed at `2016-01-04..2026-04-30` with canonical output and trial-ledger paths and no operator scope/path override; the consumed `2026-05-12..2026-08-11` master interval is never reusable; the new blind starts on/after `2026-09-08` and remains unopened. This implementation does not complete the conditional selector evidence. After exact-head acceptance/merge, the sequence is workstation `--source-only` preflight → control review → explicit `--authorize-development-outcomes` → frozen DEVELOPMENT strategy × condition evidence → walk-forward selector/profile evidence → later one-time future-blind evaluation after sufficient accrual.'''
readme_new = '''- **B35 source-only workstation preflight is ACCEPTED; DEVELOPMENT outcomes remain unopened.** On merged `main` commit `4cf27ae9d23ac3b5d1821200e4d303db787f361a`, the governed `2016-01-04..2026-04-30` preflight selected exactly `59,768` frozen minute units with source fingerprint `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`, split-evidence fingerprint `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`, and active B35 contract fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`. The preflight created no outcome authorization and opened no outcomes. Consumed-master rows permitted/read = `0/0`; future-blind rows permitted/read = `0/0`; provider calls/broker reads/broker writes = `0/0/0`; PAPER/LIVE authority = `false/false`; strategy/selector promotion remains `false/false`. The consumed `2026-05-12..2026-08-11` master interval remains permanently unavailable to B35 fitting/scoring, and the future blind beginning on/after `2026-09-08` remains unopened. The next Track-B gate is the single canonical `--authorize-development-outcomes` replay, followed by strategy × condition analysis and the preregistered walk-forward selector/profile evidence; no alternate date/output/ledger scope is permitted.'''
replace_once(README, readme_old, readme_new)

roadmap_old = '''**Authority during implementation acceptance:** no B35 historical outcomes have been opened. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER orders `0`; LIVE operations `0`; strategy promotion `false`; selector promotion `false`; PAPER authority unchanged/absent; LIVE authority `false`. DEVELOPMENT scoring ends `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval is permanently unavailable for B35 fitting/scoring/qualification; the future blind beginning on/after `2026-09-08` remains unopened.\n\nAfter exact-head implementation acceptance and merge: (1) run workstation `--source-only`; (2) review source-only evidence in the control chat; (3) only then explicitly run `--authorize-development-outcomes`; (4) materialize the frozen DEVELOPMENT opportunity/outcome evidence; (5) analyze strategy × stock-condition results; (6) build the preregistered walk-forward selector/profile evidence; (7) later evaluate the genuinely new future blind after its required accrual; and (8) never reuse the consumed master interval. Full mechanics and methodology anchors are maintained in `docs/b35_a36_preoutcome_conditional_evidence.md`.'''
roadmap_new = '''**Source-only workstation gate ACCEPTED (2026-09-08).** On merged `main` commit `4cf27ae9d23ac3b5d1821200e4d303db787f361a`, the canonical `2016-01-04..2026-04-30` source-only run selected exactly `59,768` minute units. Source fingerprint = `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`; split-evidence fingerprint = `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`; active B35 fingerprint = `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`. The run created no DEVELOPMENT outcome authorization and opened no B35 outcomes. Consumed-master rows permitted/read `0/0`; future-blind rows permitted/read `0/0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`. DEVELOPMENT scoring still ends `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval remains permanently unavailable for B35 fitting/scoring/qualification; the future blind beginning on/after `2026-09-08` remains unopened.\n\nNext Track-B sequence: (1) explicitly run the one canonical `--authorize-development-outcomes` replay; (2) preserve its immutable authorization/read-start/group-receipt/run fingerprints; (3) analyze frozen DEVELOPMENT strategy × stock-condition evidence without rescue retuning; (4) build the preregistered walk-forward selector/profile evidence; (5) later evaluate the genuinely new future blind after its required accrual; and (6) never reuse the consumed master interval. Full mechanics and methodology anchors are maintained in `docs/b35_a36_preoutcome_conditional_evidence.md`.'''
replace_once(ROADMAP, roadmap_old, roadmap_new)

EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
evidence = {
    "contract": "atlas-b35-source-only-preflight-acceptance-v1",
    "status": "ACCEPTED",
    "observed_at_date": "2026-09-08",
    "repository_main_commit": "4cf27ae9d23ac3b5d1821200e4d303db787f361a",
    "scope": {
        "start_session": "2016-01-04",
        "end_session": "2026-04-30",
        "operator_override": False,
        "source_unit_count": 59768,
    },
    "fingerprints": {
        "source": "af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd",
        "split_evidence": "3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6",
        "b35_contract": "145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6",
    },
    "authority_and_access": {
        "outcome_authorization_created": False,
        "outcomes_opened": False,
        "consumed_master_rows_permitted": 0,
        "consumed_master_rows_read": 0,
        "future_blind_rows_permitted": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
    },
    "local_evidence_paths": {
        "source_plan": r"data\v2_build\alpaca_sip_v2\derived\strategy_lab\b35_development\145cc8983439b606\2016-01-04_2026-04-30\source_plan.json",
        "split_evidence": r"data\v2_build\alpaca_sip_v2\derived\strategy_lab\b35_development\145cc8983439b606\2016-01-04_2026-04-30\split_evidence.json",
    },
    "next_gate": "single canonical --authorize-development-outcomes replay",
}
EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

SELF.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
