from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "packages/backtesting/b35_development_source.py"
text = PATH.read_text(encoding="utf-8")
old = '''    manifest_path = layout.manifests / "native_acquisition_plan.json"\n    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"\n    manifest = _read_json_object(manifest_path, "V2 native acquisition plan manifest")\n'''
new = '''    manifest_path = layout.manifests / "native_acquisition_plan.json"\n    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"\n    _assert_native_path(\n        manifest_path,\n        expected=manifest_path,\n        root=layout.root,\n        label="native acquisition plan manifest",\n    )\n    manifest = _read_json_object(manifest_path, "V2 native acquisition plan manifest")\n'''
if text.count(old) != 1:
    raise RuntimeError("expected native-plan manifest read block not found exactly once")
PATH.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
