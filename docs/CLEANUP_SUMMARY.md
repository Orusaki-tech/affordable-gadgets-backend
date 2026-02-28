# Backend cleanup summary

One-time cleanup applied to the Django backend.

## What was done

1. **README**
   - Resolved merge conflict and completed content (features, quick start, doc index).

2. **Config / secrets**
   - `.env` added to `.gitignore` so secrets are never committed (`.env.local` was already ignored).
   - Use `.env.example` and `.env.local.example` as templates.

3. **Lint / format**
   - Added `pyproject.toml` with [Ruff](https://docs.astral.sh/ruff/) config. From repo root:
     - `ruff check .`
     - `ruff format .`
   - Install with `pip install ruff` (optional, not in `requirements.txt`).

4. **Structure**
   - **scripts/adhoc/** – Moved one-off Python/JS/shell scripts (check_*, test_*, verify_*, profile_*.js, diagram scripts) here. See `scripts/adhoc/README.md`.
   - **docs/archive/** – Moved past fix summaries, diagnostics, and one-off guides (e.g. CLOUDINARY_*, FIX_*, STORAGE_*) here for reference.
   - **docs/README.md** – Index for docs and archive.

5. **Root**
   - Root now keeps: `manage.py`, `requirements.txt`, `README.md`, main guides (LOCAL_DEVELOPMENT, DEPLOYMENT, PRODUCTION_CHECKLIST, DOCKER, QUICK_START, etc.), `startup.sh`, `build.sh`, `startup_migration_check.py`, and config files.

## Optional next steps

- Run `ruff check .` and `ruff format .` and fix any issues you want to adopt.
- Delete or thin `scripts/adhoc/` and `docs/archive/` later if you don’t need the history.
