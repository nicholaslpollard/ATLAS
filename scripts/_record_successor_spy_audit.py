from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


readme = ROOT / "README.md"
replace_once(
    readme,
    "and a fixed 4x1/6x1/8x1 exact-equivalence benchmark.",
    "and an optional 4x1/6x1/8x1 exact-equivalence performance diagnostic.",
)
replace_once(
    readme,
    "The full 493-group run requires a second explicit CLI gate and remains prohibited until the workstation benchmark is accepted.",
    "The full 493-group run still requires a second explicit CLI gate, but the workstation benchmark is now an optional performance diagnostic rather than a scientific prerequisite.",
)
replace_once(
    readme,
    "The audit must resolve the complete DEVELOPMENT calendar and produce a hash-bound benchmark-source receipt before the 4x1/6x1/8x1 benchmark may run. No successor benchmark performance has been opened. Consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority remains zero/false.",
    "The source-only audit is now ACCEPTED under contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33` and scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`. It resolves all **2,596** DEVELOPMENT XNYS sessions: **2,595** use the accepted minute-primary close and exactly **one** (`2019-08-12`) uses the preregistered `NATIVE_RAW_DAILY` same-session repair because the last accepted minute is `19:31:00Z`, 28.0 minutes stale. Benchmark artifact SHA-256 = `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`; native-acceptance fingerprint = `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. PR #87 merged as `1e5c399752be690cc1b4a33e915f922e5503d956`, removing optional pandas Parquet-engine dependencies from both the source audit and successor DEVELOPMENT runner without changing scientific contracts. Consumed-master/future-blind/provider/broker reads remain `0`; PAPER/LIVE/promotion authority remains false. The next permitted evidence action is the separately authorized full 493-group standalone DEVELOPMENT run; the 4x1/6x1/8x1 benchmark remains available only as an optional performance diagnostic.",
)

roadmap = ROOT / "docs/roadmap.md"
replace_once(
    roadmap,
    "The successor 21-family/context/confluence package, exact rules/features, PR #83 portable source/runner contract, and hash-only workstation source binding are complete. PR #84 is the current Track-B implementation/acceptance gate for the separately authorized DEVELOPMENT outcome runner. After merge, the next permitted evidence action is only the frozen 4x1/6x1/8x1 workstation benchmark; the complete 493-group standalone run remains second-gated until benchmark equivalence and thermal/OS-headroom acceptance. The long-term router should",
    "The successor 21-family/context/confluence package, exact rules/features, PR #83 portable source/runner contract, hash-only workstation source binding, and the bounded SPY source-only audit are complete. PR #84 remains the Track-B DEVELOPMENT outcome runner implementation. The accepted SPY audit resolved all 2,596 DEVELOPMENT sessions with 2,595 minute-primary closes and one exact same-session raw-native-daily repair on 2019-08-12. The next permitted evidence action is the separately authorized complete 493-group standalone run. The frozen 4x1/6x1/8x1 benchmark remains available as an optional performance/equivalence diagnostic, not a scientific prerequisite. The long-term router should",
)
replace_once(
    roadmap,
    "The next gate remains the bounded exact-equivalence workstation benchmark. The full 493-group standalone DEVELOPMENT run is still prohibited until that benchmark passes and the selected worker profile is accepted. This repair grants no PAPER, LIVE, broker, provider, or promotion authority.",
    "That minute-only repair path is superseded by the accepted source-only audit described below. The full 493-group standalone DEVELOPMENT run still requires its explicit second CLI authorization, but no longer depends on completing the optional 4x1/6x1/8x1 performance benchmark first. This change affects execution governance only; it grants no PAPER, LIVE, broker, provider, or promotion authority.",
)
replace_once(
    roadmap,
    "The successor benchmark source is therefore re-gated through `run_successor_spy_source_audit.py`. The accepted B35 minute source remains primary. When a DEVELOPMENT session is missing/invalid or more than five minutes stale, the audit may use the exact same-session SPY close from the already-lineaged raw canonical V2 daily source **only for years <= 2025**. It may not open a 2026 native-daily partition; any unresolved 2026 minute session fails the audit. The audit scans the complete DEVELOPMENT calendar in one pass, records every repair, creates a hash-bound benchmark Parquet/receipt, opens no strategy outcomes, and grants no provider/broker/PAPER/LIVE/promotion authority. The 4x1/6x1/8x1 outcome benchmark remains blocked until this source-only receipt is accepted and recorded.",
    "The successor benchmark source is re-gated through `run_successor_spy_source_audit.py`. The accepted B35 minute source remains primary. When a DEVELOPMENT session is missing/invalid or more than five minutes stale, the audit may use the exact same-session SPY close from the already-lineaged raw canonical V2 daily source **only for years <= 2025**. It may not open a 2026 native-daily partition; any unresolved 2026 minute session fails the audit. The workstation audit is now **ACCEPTED**: contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33`, scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`, benchmark SHA-256 `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`, native-acceptance fingerprint `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`, and **2,596/2,596 sessions resolved**. Of those, **2,595** are minute-primary and exactly one (`2019-08-12`) is repaired from `NATIVE_RAW_DAILY`; its last accepted minute was `19:31:00Z`, 28.0 minutes stale. Authority stayed source-only with consumed-master/future/provider/broker reads `0`, PAPER/LIVE/promotion false, and strategy outcomes unopened. PR #87 subsequently removed optional pandas Parquet-engine dependencies from this audit and the downstream runner without changing scientific identity. The full standalone DEVELOPMENT run is now the next evidence gate; the 4x1/6x1/8x1 benchmark is optional.",
)

evidence = ROOT / "docs/strategy_evidence_register.md"
replace_once(
    evidence,
    "No broad successor opportunity count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The accepted sequence is: exact-head PR #84 CI and merge; bounded workstation 4x1/6x1/8x1 benchmark under `--authorize-development-outcomes --mode benchmark`; exact scientific equivalence plus thermal/OS-headroom acceptance; and only then a separately authorized full standalone DEVELOPMENT run. Consumed master and future blind remain unavailable, provider/broker/PAPER/LIVE/promotion authority remains zero/false, and no favorable DEVELOPMENT result can self-qualify a DEVELOPMENT-inspired challenger.",
    "No broad successor opportunity count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The SPY source-only audit is accepted and the next evidence gate is the separately authorized full standalone DEVELOPMENT run. The 4x1/6x1/8x1 benchmark remains available as an optional operational performance/equivalence diagnostic and is no longer a scientific prerequisite. Consumed master and future blind remain unavailable, provider/broker/PAPER/LIVE/promotion authority remains zero/false, and no favorable DEVELOPMENT result can self-qualify a DEVELOPMENT-inspired challenger.",
)
replace_once(
    evidence,
    "Consumed-master rows read: 0. Future-blind rows read: 0. Provider calls: 0. Broker reads/writes: 0/0. PAPER/LIVE/promotion authority: false/false/false. The next scientific action remains the bounded workstation equivalence benchmark; broad 493-group DEVELOPMENT outcomes remain unopened.",
    "Consumed-master rows read: 0. Future-blind rows read: 0. Provider calls: 0. Broker reads/writes: 0/0. PAPER/LIVE/promotion authority: false/false/false. This minute-only preparation path is historical; the accepted source-only audit below supersedes it. Broad 493-group DEVELOPMENT outcomes remain unopened.",
)
replace_once(
    evidence,
    "ATLAS will not widen the minute tolerance to disguise this source gap. A new source-only audit is required instead. Minute data remains the primary benchmark source; only a minute session that is missing, invalid, or >5 minutes stale may be repaired from the exact same-session raw canonical V2 daily SPY close, and daily repair is hard-limited to years <=2025. The 2026 native-daily partition is forbidden so no consumed-master rows can be touched indirectly. The audit must resolve every DEVELOPMENT XNYS session, bind exact source/file hashes into a receipt, and preserve consumed-master/future/provider/broker reads at 0 with PAPER/LIVE/promotion false. Broad successor outcomes remain unopened.",
    "ATLAS did not widen the minute tolerance to disguise this source gap. The source-only audit retained minute data as primary; only a minute session that is missing, invalid, or >5 minutes stale may be repaired from the exact same-session raw canonical V2 daily SPY close, with daily repair hard-limited to years <=2025. The 2026 native-daily partition remains forbidden. The workstation audit is now **ACCEPTED** under contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33` and scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`. It resolves all **2,596** DEVELOPMENT sessions: **2,595** minute-primary and one `NATIVE_RAW_DAILY` repair for `2019-08-12`, whose last accepted minute was `19:31:00Z` and 28.0 minutes stale. Benchmark SHA-256 is `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`; native-acceptance fingerprint is `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. Consumed-master/future/provider/broker reads remained 0, PAPER/LIVE/promotion remained false, and strategy outcomes remained unopened. PR #87 merged the DuckDB-only Parquet portability repair without changing these scientific identities. Broad successor outcomes are still unopened; the next permitted evidence action is the explicitly authorized full 493-group standalone run, with the 4x1/6x1/8x1 benchmark retained only as an optional diagnostic.",
)

print("recorded accepted successor SPY audit and optionalized performance benchmark governance")
