# ATLAS Phase 01 — Foundation & Canonical Contracts

**A.T.L.A.S. — Autonomous Trading, Learning & Analysis System**

Phase 01 establishes the contracts that every later ATLAS subsystem will use. It does **not** download market data or trade. It provides configuration, secret handling, time/session logic, canonical market schemas, ingestion schemas, data-quality schemas, and validation tests.

## What this phase installs

- `config/` — base configuration and environment overlays.
- `packages/core/` — shared enums, settings, secrets, timestamps, calendar helpers, identifiers, validation.
- `packages/schemas/` — canonical market, ingestion, and data-quality schemas.
- `scripts/validate_foundation.py` — validates configuration and core session/calendar behavior.
- `tests/unit/` — unit tests for the Phase 01 foundation.
- `docs/` — locked data architecture and ingestion contracts.

## Before installation

1. Rotate any Massive/API credentials that were present in the legacy Chart Monitor archive.
2. Never copy legacy credentials into ATLAS source code.
3. Keep your real `.env` out of Git.

## Install

Extract this ZIP **into the existing `ATLAS/` root** so that `config/`, `packages/`, `tests/`, etc. merge with the structure you already created.

From the ATLAS root:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

Linux/WSL/macOS:

```bash
source .venv/bin/activate
```

Then install Phase 01 dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.lock
pip install -e .
```

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows Command Prompt:

```cmd
copy .env.example .env
```

Do not add actual API keys until the provider phase unless you want to prepare them now.

## Validate

```bash
python scripts/validate_foundation.py
pytest -q tests/unit/test_core_settings.py tests/unit/test_core_time.py tests/unit/test_market_schema.py tests/unit/test_ingestion_schema.py tests/unit/test_data_quality_schema.py
```

Expected result: all Phase 01 tests pass.

## Phase 01 decisions encoded here

- UTC is the canonical timestamp standard.
- `America/New_York` is the market-local timezone.
- XNYS is the initial U.S. equity trading calendar.
- Regular-session derived bars are anchored to the actual exchange session open rather than arbitrary wall-clock floors.
- Extended-hours data is preserved but is not mixed into regular-session 15m/1h/4h bars.
- Provider/source facts are separated from derived features and strategy state.
- Ingestion is designed to be idempotent, restartable, and manifest/checkpoint driven.
- No secrets are stored in source code.

## Next phase

Phase 02 will implement the Massive provider adapter and incremental ingestion ledger/planner/downloader.
