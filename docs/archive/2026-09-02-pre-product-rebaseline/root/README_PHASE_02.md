# ATLAS Phase 02 — Massive Flat-File Ingestion

Phase 2 adds restartable, idempotent Massive stock aggregate ingestion.

## New capabilities

- Massive S3-compatible client using environment-only credentials
- Remote flat-file inventory by actual provider objects
- XNYS-session-aware missing-file reporting
- Per-source atomic ingestion manifests
- Atomic `.part` downloads with SHA-256 during transfer
- Byte-size validation against provider metadata
- gzip CRC and CSV-header validation
- retry/backoff behavior
- checkpointing after successful validation
- dry-run planning
- interruption/resume integration tests
- idempotent reruns

## Credentials

Set only the credential variables you actually use. Do not place secret values in
YAML or Python source.

```powershell
$env:MASSIVE_S3_ACCESS_KEY_ID="..."
$env:MASSIVE_S3_SECRET_ACCESS_KEY="..."
```

The REST API key is not required for Flat Files in this phase.

## Install/update dependencies

From the ATLAS root with the virtual environment active:

```powershell
pip install -r requirements.lock
pip install -e .
```

## Run all tests

```powershell
pytest -q
```

## Dry-run a synchronization

```powershell
python scripts/sync_missing_massive_data.py --dataset day --start 2026-08-03 --end 2026-08-14 --dry-run
```

Minute aggregates:

```powershell
python scripts/sync_missing_massive_data.py --dataset minute --start 2026-08-03 --end 2026-08-14 --dry-run
```

## Download a deliberately small test

Use `--max-files 1` for the first real provider test:

```powershell
python scripts/sync_missing_massive_data.py --dataset day --start 2026-08-14 --end 2026-08-14 --max-files 1
```

Run the exact command again. The second run should report zero planned downloads.

## Validate tracked provider files

```powershell
python scripts/validate_provider_files.py --dataset day
```

## Important boundary

Phase 2 stops after the validated provider archive. It does **not** build ATLAS
canonical Parquet or derived 15m/1h/4h bars. Those are Phase 3 so we can test the
download/recovery layer independently from data transformation.
