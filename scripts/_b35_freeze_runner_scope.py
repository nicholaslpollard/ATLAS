from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one match")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "scripts/run_b35_development_replay.py",
    '''    parser.add_argument("--start", type=date.fromisoformat, default=V2_DEFAULT_START)\n    parser.add_argument(\n        "--end",\n        type=date.fromisoformat,\n        default=DEVELOPMENT_LAST_SCORING_SESSION,\n    )\n    parser.add_argument("--output-root", type=Path, default=None)\n    parser.add_argument("--trial-ledger", type=Path, default=None)\n''',
    '''    # The governed B35 trial has one frozen scope and one canonical evidence/ledger\n    # location. Operator-selectable slices or alternate ledgers would create an\n    # avoidable data-snooping/audit bypass surface.\n''',
)
replace_once(
    "scripts/run_b35_development_replay.py",
    '''    settings = load_settings(PROJECT_ROOT)\n    source = B35DevelopmentMinuteSource(settings)\n    plan = source.plan(args.start, args.end)\n''',
    '''    start = V2_DEFAULT_START\n    end = DEVELOPMENT_LAST_SCORING_SESSION\n    settings = load_settings(PROJECT_ROOT)\n    source = B35DevelopmentMinuteSource(settings)\n    plan = source.plan(start, end)\n''',
)
replace_once(
    "scripts/run_b35_development_replay.py",
    '''    output_root = (\n        Path(args.output_root).resolve()\n        if args.output_root is not None\n        else _output_root(settings, args.start, args.end)\n    )\n''',
    '''    output_root = _output_root(settings, start, end)\n''',
)
replace_once(
    "scripts/run_b35_development_replay.py",
    '''    print(f"  scope: {args.start} -> {args.end}")\n''',
    '''    print(f"  scope: {start} -> {end} (frozen; no operator override)")\n''',
)
replace_once(
    "scripts/run_b35_development_replay.py",
    '''    ledger = StrategyTrialLedger(\n        Path(args.trial_ledger).resolve()\n        if args.trial_ledger is not None\n        else _ledger_path(settings)\n    )\n    token = f"{args.start:%Y%m%d}_{args.end:%Y%m%d}.{input_fingerprint[:12]}"\n''',
    '''    ledger = StrategyTrialLedger(_ledger_path(settings))\n    token = f"{start:%Y%m%d}_{end:%Y%m%d}.{input_fingerprint[:12]}"\n''',
)

replace_once(
    "README.md",
    '''DEVELOPMENT scored outcomes still end `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval is never reusable;''',
    '''The governed finite replay scope is fixed at `2016-01-04..2026-04-30` with canonical output and trial-ledger paths and no operator scope/path override; the consumed `2026-05-12..2026-08-11` master interval is never reusable;''',
)
replace_once(
    "docs/roadmap.md",
    '''**Finite replay implementation boundary.** The implementation binds the exact DEVELOPMENT minute-unit set to the immutable native acquisition plan and exact `year/month/batch/unit` checkpoint/canonical paths.''',
    '''**Finite replay implementation boundary.** The governed replay is one canonical trial over `2016-01-04..2026-04-30`; the CLI exposes no alternate start/end, output-root, or trial-ledger override. The implementation binds that exact DEVELOPMENT minute-unit set to the immutable native acquisition plan and exact `year/month/batch/unit` checkpoint/canonical paths.''',
)
replace_once(
    "docs/roadmap.md",
    '''Only after that separate review may `--authorize-development-outcomes` explicitly open the finite frozen DEVELOPMENT replay through `2026-04-30`;''',
    '''Only after that separate review may `--authorize-development-outcomes` explicitly open the one canonical frozen DEVELOPMENT replay over `2016-01-04..2026-04-30`;''',
)
replace_once(
    "docs/b35_a36_preoutcome_conditional_evidence.md",
    '''The replay source is not a second data lake. It binds the exact expected 1-minute unit set to the immutable V2 native acquisition plan,''',
    '''The replay source is not a second data lake. The governed replay scope is exactly **2016-01-04 through 2026-04-30**, with canonical output and trial-ledger locations and no operator-selectable scope/path override. It binds the exact expected 1-minute unit set to the immutable V2 native acquisition plan,''',
)
