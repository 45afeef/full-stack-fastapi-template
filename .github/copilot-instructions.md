<!--
Purpose: Short, actionable guidance for AI coding assistants working on this repository.
Keep it concise (20-50 lines). Reference concrete files/commands and patterns discovered in the codebase.
-->

# Copilot / AI Assistant Instructions

Be direct and conservative: make small, well-tested changes and reference the project's existing patterns.

1. Big picture
   - Backend: FastAPI app under `backend/app/`. Config and runtime settings live in `backend/app/core/` (see `core/config.py` and `core/db.py`).
   - Frontend: Vite + React TypeScript under `frontend/src/`. Client SDKs and generated types are under `frontend/src/client`.
   - Dev infra: `docker-compose.yml`, and development overrides in `docker-compose.override.yml`. Use containers for consistent local runs.

2. Key files to read before editing
   - `backend/README.md` — developer workflows, test and migration commands.
   - `backend/pyproject.toml` — pinned dependencies, lint/test tools (uv, pytest, ruff, mypy).
   - `backend/app/main.py` — app creation, router inclusion, custom route id generation.
   - `backend/app/alembic/` — migrations are managed with alembic (create revision + `alembic upgrade head`).

3. Concrete developer workflows (discoverable commands)
   - Install/sync dependencies (backend): `uv sync` (from `backend/`) and activate venv: `source .venv/bin/activate`.
   - Run backend in development (inside container): `fastapi run --reload app/main.py` (container `backend` path is `/app`).
   - Run backend tests: `bash ./backend/scripts/test.sh` (or inside container: `docker compose exec backend bash scripts/tests-start.sh`).
   - Create and apply migrations inside the backend container with Alembic: `alembic revision --autogenerate -m "msg"` and `alembic upgrade head`.

4. Project-specific patterns and conventions
   - Models use SQLModel (see `pyproject.toml` and `backend/app/models/`); migrations are kept under `backend/app/alembic/versions/`.
   - Settings are centralized: prefer reading/writing through `app.core.config.settings`.
   - Route unique IDs use the tag-based function in `backend/app/main.py` (unique id = `{tag}-{route.name}`) — keep tags present on routers.
   - Tests are under `backend/tests/`; coverage artifacts are generated into `backend/htmlcov/`.

5. Style, linting and typing
   - This repo enforces `mypy`, `ruff`, and `pre-commit` (see `backend/pyproject.toml`). Follow existing typing style and run linters locally when you change behavior.

6. Safe change checklist for PRs
   - Small, focused commits with tests. Run `bash backend/scripts/test.sh` locally for backend changes.
   - For DB model changes: create alembic revision and add generated revision files to the commit.
   - Preserve existing settings usages (don't hardcode secrets). Use `settings.*` and `.env` in dev flows.

7. When touching the frontend
   - Check `frontend/README.md`. Frontend uses Vite and Playwright; e2e tests live in `frontend/tests` (see Playwright config).
   - If API surface changes, update the generated client under `frontend/src/client` (there's a generation script in `scripts/generate-client.sh`).

If anything above is unclear or you need a missing command/example added, ask for the exact scenario and I will update this file.
