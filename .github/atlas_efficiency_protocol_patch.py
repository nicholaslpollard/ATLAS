from pathlib import Path

README = Path("README.md")
ROADMAP = Path("docs/roadmap.md")


def replace_prefixed_line(text: str, prefix: str, replacement: str) -> str:
    lines = text.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one line beginning {prefix!r}; found {len(matches)}")
    lines[matches[0]] = replacement
    return "\n".join(lines) + "\n"


readme = README.read_text(encoding="utf-8")
readme = replace_prefixed_line(
    readme,
    "- **B35 observable parallel DEVELOPMENT replay performance package",
    "- **B35 observable parallel DEVELOPMENT replay performance package is MERGED / CANONICAL REPLAY RUNNING.** PR #72 merged to `main` as `4a2ec3fcfb33c375a7b883ae8b3473e82fa29f6f`. The accepted fastest tested workstation shape is **10 worker processes x 1 DuckDB thread**, with process-local DuckDB/calendar reuse and `itertuples()` canonical-bar conversion while retaining full `CanonicalBar.model_validate()` for every minute bar. Its final isolated real-data probe passed **10/10 exact JSONL SHA-256 comparisons** at **2,942.2 source units/hour**, projecting **20.3 hours full / 16.9 hours remaining** from the preserved restart point, versus the measured serial restart rate of about **660.6 units/hour / 77.5 hours remaining**: roughly a **4.45x throughput improvement** without changing scientific output. The single-Parquet-scan experiment was rejected after exact-equivalent output regressed to 820.8 units/hour. The canonical replay is now resumed from **82 validated completed groups / 10,168 units**, reusing the immutable authorization/trial and preserving consumed-master/future-blind reads at zero. Final canonical runtime/throughput remains pending and will be recorded after completion; interim progress telemetry is operational, not scientific evidence."
)

readme_marker = "## How progress is reported\n\n"
protocol = """### Reusable validated performance-optimization protocol

The B35 replay established the default ATLAS pattern for expensive deterministic or research workloads. Apply the same pattern, adapted to the workload's own correctness contract, to historical replays, data builds, validation passes, simulations, feature generation, large audits, and other batch work where runtime becomes material:

1. **Instrument before optimizing.** Establish a real baseline on the target workstation: completed work unit, elapsed time, throughput, ETA, worker/thread shape, and restart state. Do not optimize from intuition alone.
2. **Make the job restartable first.** Preserve atomic checkpoints, self-hash receipts, immutable input fingerprints, and validated completed work so experiments or interruptions never require discarding good canonical progress.
3. **Separate science/correctness from execution.** Frozen strategy rules, source scope, validators, outcome mechanics, authority, and final scientific fingerprints must not change merely to improve speed. Runtime metadata and completion order are non-authoritative.
4. **Profile the actual bottleneck.** Test concurrency, I/O shape, Python/object overhead, reusable process-local resources, and data-layout costs independently. More threads or fewer scans are not assumed faster; B35 demonstrated both diminishing concurrency returns and a major single-scan regression.
5. **Use isolated golden-output probes.** Recompute already completed canonical work in a temporary location and require the strongest available equivalence evidence—preferably byte-identical output hashes plus receipt/scientific-field parity—before an optimization may touch the canonical continuation path.
6. **Change one execution layer at a time.** Keep experiments narrow enough that gains or regressions have an attributable cause and can be cleanly reverted.
7. **Tune the real hardware empirically.** Benchmark worker x library-thread combinations on the actual host while reserving enough CPU/RAM/I/O headroom for the OS, remote administration, and coordinator. Keep the fastest scientifically equivalent measured shape, not the configuration that merely looks most parallel.
8. **Reuse infrastructure, not evidence shortcuts.** Safe examples include process-local database connections, immutable calendars, compiled/read-only helpers, and bounded non-scientific caches. Do not bypass source hashes, validators, checkpoint verification, protected-data boundaries, or required model/schema validation solely for speed.
9. **Reject regressions explicitly.** Preserve benchmark evidence for failed ideas so future work does not repeat them. Exact equivalence is necessary but not sufficient: a slower equivalent implementation is rejected unless it solves another material operational problem.
10. **Stop optimizing when execution is tractable.** Among accepted candidates, use the fastest measured scientifically equivalent implementation. Continue searching only when the projected time saved reasonably exceeds the engineering and revalidation cost or a clearly larger safe gain is available.
11. **Resume; do not restart.** Once the execution path is accepted, continue the canonical job from all validated receipts/checkpoints. Benchmark recomputes remain isolated and never advance or erase canonical progress.
12. **Close the loop with real-run evidence.** After the canonical workload completes, record final elapsed time, sustained throughput, interruptions/restarts, resource shape, and any difference from benchmark projections. Use that case history to size and design future long-running ATLAS work.

For B35 specifically, the measured path moved from about **660.6 units/hour** in the serial restart to a final isolated exact-equivalent benchmark of **2,942.2 units/hour** at 10 x 1, while preserving **10/10 byte-identical sampled outputs** and all scientific/authority boundaries. This is the reference case for the protocol; its final canonical real-run result will be added after completion.

"""
if readme_marker not in readme:
    raise RuntimeError("README progress marker not found")
if "### Reusable validated performance-optimization protocol" not in readme:
    readme = readme.replace(readme_marker, readme_marker + protocol, 1)
README.write_text(readme, encoding="utf-8")

roadmap = ROADMAP.read_text(encoding="utf-8")
roadmap = replace_prefixed_line(
    roadmap,
    "7. **CURRENT Track-B gate",
    "7. **CURRENT Track-B gate — complete the resumed canonical B35 DEVELOPMENT replay using the accepted execution path.** PR #72 is merged as `4a2ec3fcfb33c375a7b883ae8b3473e82fa29f6f`. The fastest tested scientifically equivalent workstation configuration is **10 workers x 1 DuckDB thread** with process-local DuckDB/calendar reuse and `itertuples()` canonical-bar conversion while retaining full per-minute `CanonicalBar.model_validate()`. The final isolated real-data probe passed **10/10 exact JSONL SHA-256 comparisons** at **2,942.2 units/hour**, versus about **660.6 units/hour** on the measured serial restart, approximately **4.45x faster**. The canonical run has resumed from **82 validated groups / 10,168 units** under the unchanged authorization `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`, trial `b35.dev.20160104_20260430.eb3b7ff9f417.registration`, frozen `2016-01-04..2026-04-30` source, zero consumed-master/future-blind reads, and zero provider/broker/PAPER/LIVE or promotion authority. Final canonical runtime/throughput will be recorded on completion; after successful B35 completion, proceed to strategy x condition evidence and the preregistered selector."
)
roadmap_marker = "## 20. Phase/package cadence and progress reporting\n\n"
roadmap_protocol = """### Validated efficiency protocol for long-running ATLAS work

B35 establishes a reusable engineering gate for runtime-sensitive deterministic and research workloads. Future packages should adapt this pattern to their own correctness contract rather than copying B35 mechanics blindly:

- capture real target-hardware baseline throughput and restart state before optimization;
- make canonical work atomic, restartable, and receipt/checkpoint validated before performance experimentation;
- keep scientific/correctness semantics and runtime mechanics explicitly separated;
- benchmark plausible bottlenecks independently, including process concurrency, library threading, storage scans, Python/object conversion, and safe process-local resource reuse;
- run optimization candidates against isolated completed golden work and require the strongest practical equivalence proof, with exact output hashes plus scientific receipt-field parity preferred for deterministic artifacts;
- change one execution layer per experiment, reject regressions, and retain enough evidence to prevent repeating failed approaches;
- empirically choose the fastest scientifically equivalent worker/thread/resource shape on the actual host while preserving OS/operator headroom;
- permit reusable operational infrastructure but never trade away source/hash verification, fail-closed validators, protected-data controls, required schema/model validation, or authority boundaries for speed;
- keep all benchmark/progress artifacts non-authoritative and prevent parallel completion order from becoming scientific ordering;
- once accepted, resume the canonical workload from every valid checkpoint rather than rebuilding successful work; and
- after completion, record actual sustained runtime/throughput and compare it with the probe so future workload sizing uses observed evidence.

The B35 reference case improved the measured serial restart from about **660.6 units/hour** to an isolated exact-equivalent **2,942.2 units/hour** at 10 x 1, roughly **4.45x faster**, while preserving 10/10 sampled output hashes and all frozen scientific and authority semantics. A seemingly attractive single-Parquet-scan rewrite was retained as a negative optimization result because it fell to **820.8 units/hour** despite exact equivalence. This combination—measure, isolate, prove equivalence, benchmark, reject regressions, preserve restart state, then resume—is the default ATLAS efficiency pattern when long-running work becomes a material project bottleneck.

"""
if roadmap_marker not in roadmap:
    raise RuntimeError("roadmap cadence marker not found")
if "### Validated efficiency protocol for long-running ATLAS work" not in roadmap:
    roadmap = roadmap.replace(roadmap_marker, roadmap_marker + roadmap_protocol, 1)
ROADMAP.write_text(roadmap, encoding="utf-8")
