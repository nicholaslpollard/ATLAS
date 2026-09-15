from pathlib import Path

analysis = Path('packages/backtesting/successor_selected_daily_path_analysis.py')
text = analysis.read_text(encoding='utf-8')
old = '''def selected_daily_path_root(project_root: Path) -> Path:\n    return (\n        optionworthiness_root(project_root)\n        / "selected_daily_path_v1"\n        / SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT[:16]\n    ).resolve()\n'''
new = '''def selected_daily_path_root(project_root: Path) -> Path:\n    # Keep derived path artifacts beside, rather than beneath, option-worthiness.\n    # The scientific binding to the accepted option-worthiness run is validated\n    # separately in _validate_optionworthiness(); nesting it here needlessly pushed\n    # Windows atomic destinations beyond legacy-safe path lengths.\n    return (\n        conditioning_root(project_root)\n        / "selected_daily_path_v1"\n        / SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT[:16]\n    ).resolve()\n'''
if old not in text:
    raise SystemExit('selected_daily_path_root anchor missing or already changed')
analysis.write_text(text.replace(old, new), encoding='utf-8')

test = Path('tests/test_successor_selected_daily_path_analysis.py')
t = test.read_text(encoding='utf-8')
t = t.replace('from pathlib import Path\n', 'from pathlib import Path, PureWindowsPath\n')
t = t.replace(
    '    _threshold_query,\n)',
    '    _threshold_query,\n    selected_daily_path_root,\n)'
)
t = t.replace(
    'from packages.strategies.successor_selected_daily_path_contract import (',
    'from packages.backtesting.successor_optionworthiness_analysis import conditioning_root\nfrom packages.strategies.successor_selected_daily_path_contract import ('
)
addition = '''\n\ndef test_output_root_stays_windows_legacy_safe(tmp_path: Path) -> None:\n    root = selected_daily_path_root(tmp_path)\n    conditioning = conditioning_root(tmp_path)\n    assert root.parent.parent == conditioning\n    assert "optionworthiness_v1" not in root.parts\n\n    relative = root.relative_to(tmp_path.resolve())\n    representative = PureWindowsPath(\n        r"C:\\Users\\cyberdyne\\Desktop\\ATLAS",\n        *relative.parts,\n        "selected_daily_path_contract.json",\n    )\n    assert len(str(representative)) <= 248\n'''
if 'test_output_root_stays_windows_legacy_safe' not in t:
    t = t.rstrip() + addition.rstrip() + '\n'
test.write_text(t, encoding='utf-8')

Path('.github/workflows/_temporary_fix_selected_daily_path_windows_layout.yml').unlink(missing_ok=True)
Path(__file__).unlink(missing_ok=True)
