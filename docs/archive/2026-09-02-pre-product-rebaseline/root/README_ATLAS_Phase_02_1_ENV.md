# ATLAS Phase 02.1 — Local `.env` Loading

This patch adds automatic loading of `ATLAS/.env` for local development.

## Secret precedence

1. Existing process/cloud environment variables
2. Values loaded from the repository-root `.env`
3. No hard-coded fallback values

`python-dotenv` is called with `override=False`, so production/container/cloud
environment variables remain authoritative.

## Expected local `.env`

```dotenv
ATLAS_ENV=development

MASSIVE_API_KEY=...
MASSIVE_S3_ACCESS_KEY_ID=...
MASSIVE_S3_SECRET_ACCESS_KEY=...

OPENAI_API_KEY=
DATABASE_URL=
```

Massive's non-secret flat-file endpoint and bucket remain in `config/massive.yaml`
rather than `.env`.

## Install/update

From the ATLAS root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e .
```

## Validate

```powershell
.\.venv\Scripts\python.exe scripts\validate_foundation.py
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result: `28 passed`.
