<!--
Purpose: Comprehensive guidance for AI coding assistants working on the backend service.
Reference concrete files/commands and patterns discovered in the codebase.
Focus on backend architecture, design patterns, and development workflows.
-->

# Copilot / AI Assistant Instructions

Be direct and conservative: make small, well-tested changes and reference the project's existing patterns.

## 1. Big Picture

### Backend Architecture Overview
The backend is a FastAPI-based service providing a travel booking API with user authentication, service providers, and booking management. It uses SQLModel for ORM, PostgreSQL for data persistence, and follows a modular architecture.

**Application Structure:**
```
backend/app/
├── main.py              # FastAPI app instantiation, router inclusion, custom unique ID generation
├── api/
│   ├── main.py          # Routes aggregator
│   ├── deps.py          # FastAPI dependencies (SessionDep, TokenDep, CurrentUser, auth)
│   └── routes/          # Endpoint implementations (auth, CRUD for each domain)
├── core/
│   ├── config.py        # Settings via Pydantic (reads from ../.env)
│   ├── db.py            # SQLModel engine, init_db() with superuser bootstrap
│   └── security.py      # JWT token creation, password hashing (bcrypt), verification
├── models/
│   ├── user/            # User, Profile, PhoneNumber (Pydantic + SQLModel hybrid)
│   └── travel/          # Cab, Driver, StayUnit, Booking, Agency, Provider models
├── crud.py              # Data mutation layer (create/update/delete)
├── utils.py             # Email, password reset token utilities
├── backend_pre_start.py # DB connection retry logic (runs before app start)
└── initial_data.py      # Bootstrap first superuser
```

**Data Flow:**
HTTP Request → Router (api/routes/*.py) → Dependencies (api/deps.py: SessionDep, CurrentUser) → CRUD operations (crud.py) with Session → SQLModel models (models/) ↔ PostgreSQL → Response schema (Pydantic validation)

**Dev Infra:** `docker-compose.yml` and overrides for consistent containerized development.

## 2. Key Files to Read Before Editing
- `backend/README.md` — Developer workflows, test and migration commands.
- `backend/pyproject.toml` — Pinned dependencies, lint/test tools (uv, pytest, ruff, mypy).
- `backend/app/main.py` — App creation, router inclusion, custom route ID generation.
- `backend/app/alembic/` — Migrations managed with Alembic.
- `backend/app/core/config.py` — Centralized settings and environment variables.
- `backend/app/core/db.py` — Database connection and initialization.
- `backend/app/api/deps.py` — Dependency injection patterns (SessionDep, CurrentUser).
- `backend/app/models/user/user.py` — Example of Pydantic+SQLModel hybrid models.
- `backend/app/crud.py` — Data mutation patterns.
- `backend/tests/conftest.py` — Test fixtures and database cleanup.

## 3. Concrete Developer Workflows (Discoverable Commands)
All commands run from `backend/` directory unless in container.

- **Setup:** `uv sync` (install/sync deps) and `source .venv/bin/activate` (activate venv).
- **Run Backend:** Local: `fastapi dev app/main.py`; In container: `fastapi run --reload app/main.py`.
- **Tests:** `bash ./scripts/test.sh` (full suite with coverage); In container: `bash scripts/tests-start.sh`.
- **Migrations:** In container: `alembic revision --autogenerate -m "msg"` and `alembic upgrade head`.

## 4. Project-Specific Patterns and Conventions
- **Models:** Use SQLModel for ORM; migrations in `backend/app/alembic/versions/`.
- **Settings:** Centralized via `app.core.config.settings`; never hardcode secrets.
- **Route IDs:** Generated as `{tag}-{route.name}`; routers must have `tags=["tag_name"]`.
- **Auth:** Phone-based authentication instead of email; JWT tokens via `core/security.py`.
- **UUIDs:** All primary keys use `uuid.uuid4()`.
- **Timestamps:** Automatic `created_at`, `updated_at` on all models with server-side defaults.
- **CRUD Isolation:** All mutations through `crud.py`; routes call CRUD, not direct DB ops.
- **Dependencies:** Injection via `api/deps.py` for sessions and current user.
- **Tests:** Under `backend/tests/`; fixtures provide DB cleanup.

## 5. Architecture Decisions & Component Boundaries

| Component | Purpose | Key Files | Boundaries |
|-----------|---------|-----------|------------|
| **Config** | Environment variables, validation | `core/config.py` | Single source of truth; all config flows here |
| **Database** | Connection, engine, initialization | `core/db.py` | Handles SQLModel metadata, superuser bootstrap |
| **Security** | Auth tokens, password hashing | `core/security.py` | JWT creation, bcrypt verification |
| **Dependencies** | Session injection, current user | `api/deps.py` | Injection mechanism for all endpoints |
| **CRUD** | Data mutations | `crud.py` | All CREATE/UPDATE/DELETE operations |
| **Routes** | HTTP endpoints, business logic | `api/routes/*.py` | Endpoint implementation, calls CRUD |
| **Models** | Data schemas | `models/` | Pydantic+ORM hybrids, relationships |

## 6. Potential Pitfalls & Environment Issues
- **Models not imported:** Ensure `from app.models import *` in `alembic/env.py` for autogenerate.
- **Syntax errors:** Fix before reload; container may exit.
- **Missing migrations:** Always create/commit migrations for model changes.
- **Settings validation:** Override secrets in `.env` for production.
- **CORS:** Auto-adds frontend host; check `config.py`.
- **Test state:** Fixtures cleanup tables; ensure proper model list in conftest.
- **Venv Python:** Point editor to `.venv/bin/python`.

## 7. Style, Linting and Typing
- Enforces `mypy`, `ruff`, `pre-commit` (see `backend/pyproject.toml`).
- Follow existing typing style; run linters locally.

## 8. Safe Change Checklist for PRs
- Small, focused commits with tests. Run `bash backend/scripts/test.sh` for backend changes.
- For DB model changes: create Alembic revision and commit generated files.
- Preserve settings usages; use `settings.*` and `.env`.

If anything above is unclear or you need a missing command/example added, ask for the exact scenario and I will update this file.
