# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Monorepo with two first-class apps plus specs:

- `backend/` — FastAPI + SQLAlchemy async + Alembic + Celery + Redis + MySQL 8
- `frontend/` — Vue 3 + Vite + TypeScript + Pinia + Axios (dev server proxies `/api` and `/static` → `127.0.0.1:8000`)
- `docs/superpowers/specs/` — authoritative design specs (MVP backend/frontend)
- `docs/superpowers/plans/` — per-milestone implementation plans (M1, M2, M3a)
- `product/` — product-level HTML/CSS demo; source of truth for styling tokens migrated into `frontend/src/styles/`
- `docs/huawei_api/`, `docs/huoshan_api/`, `docs/integrations/` — upstream vendor API notes (Huawei OBS, Volcengine Ark, etc.)

The project is delivered in milestones: **M1** backbone & project CRUD, **M2** novel parse + storyboard edit (mock Volcano), **M3a** real Volcengine Ark + asset library + Huawei OBS. When reading code, always check which milestone-era a file belongs to via `backend/README.md` and the plan files.

## Backend (`backend/`)

### Environment

- **Python 3.12 is required.** 3.13 is incompatible with pinned `pydantic-core==2.16.3` (Rust build fails).
- Virtualenv: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`. If `pip install` errors with `socksio`, `unset all_proxy ALL_PROXY` first (local SOCKS proxy interference).
- All test / script invocations should go through `./.venv/bin/<tool>` to avoid picking up a system Python.

### Config (`app/config.py`, `.env`)

Settings are assembled from **component** env vars, not full URLs. Never put `DATABASE_URL` / `REDIS_URL` / `CELERY_BROKER_URL` directly in `.env` — they are computed properties on `Settings`.

- MySQL: `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`, plus `MYSQL_DATABASE_TEST` (**must differ from `MYSQL_DATABASE`**; tests DROP/CREATE/TRUNCATE it).
- Redis: `REDIS_HOST/PORT`, split DBs `REDIS_DB` (app) / `REDIS_DB_BROKER` (celery broker) / `REDIS_DB_RESULT` (celery results), defaulting to 0/1/2.
- AI provider: `AI_PROVIDER_MODE=mock` (M2 default) or `real` (M3a, needs `ARK_API_KEY`, `ARK_CHAT_MODEL`, `ARK_IMAGE_MODEL`).
- Volcengine asset library: `VOLC_ACCESS_KEY_ID` / `VOLC_SECRET_ACCESS_KEY` (HMAC-SHA256 signed).
- Huawei OBS: `OBS_AK/SK/ENDPOINT/BUCKET/PUBLIC_BASE_URL`; `OBS_MOCK=true` only for tests.

### Common commands

```bash
cd backend

# Migrations (run from backend/; alembic.ini pins script_location)
alembic upgrade head
alembic revision -m "<message>"         # author new migration

# API dev server
uvicorn app.main:app --reload --port 8000
# For local pipeline runs without a celery worker, run tasks inline:
CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload

# Celery workers (two queues: ai and video)
celery -A app.tasks.celery_app worker -Q ai    -c 4 --loglevel=info
celery -A app.tasks.celery_app worker -Q video -c 2 --loglevel=info

# Tests
./.venv/bin/pytest -v                                          # full suite (~5 min over network MySQL)
./.venv/bin/pytest tests/unit/                                  # fast, no DB
./.venv/bin/pytest tests/integration/test_projects_api.py       # single file
./.venv/bin/pytest tests/integration/test_projects_api.py::test_create_project  # single test

# Lint / type-check
ruff check app tests
mypy                                                            # config in pyproject.toml

# Smoke scripts (require API running on :8000 and jq)
./scripts/smoke_m1.sh                    # health + project CRUD + rollback
./scripts/smoke_m2.sh                    # parse novel + storyboard edit
./scripts/smoke_m3a.sh <PROJECT_ID>      # full M3a chain: characters → scenes → bind → aggregate
```

### Architecture

Strict layering — the boundaries are load-bearing, not stylistic:

```
app/api/*            thin FastAPI routers; only parse/validate + delegate
app/domain/schemas/* Pydantic I/O models (request/response DTOs, ProjectRead aligns with frontend ProjectData)
app/domain/services/* business logic; MUST NOT mutate state machine fields directly
app/domain/models/*  SQLAlchemy ORM (Project, Job, StoryboardShot, Character, Scene, ShotRender, ExportTask)
app/pipeline/        state machines + the ONLY writers of stage/status fields
app/infra/           external adapters: db, redis, volcano_client, volcano_asset_client, obs_store, asset_store
app/tasks/           Celery app + task modules (ai/, video/ ...); routed by task name prefix
```

**Critical invariant — `pipeline/transitions.py` is the single writer of `project.stage`.** Every stage mutation (advance, rollback, lock_protagonist, etc.) goes through a helper in that file, which enforces the 7-state forward/rollback DAG and cascades invalidation of dependent rows (shot render resets, scene/character unlocks). Services and routers must not assign to `project.stage` directly. Similarly, `update_job_progress` is the only allowed writer of `jobs.status/progress/done/total`, and it enforces a `queued → running → (succeeded|failed|canceled)` transition table.

**Stage model** (`app/pipeline/states.py`):

```
draft → storyboard_ready → characters_locked → scenes_locked
      → rendering → ready_for_export → exported
```

- Forward transitions allow **exactly one step**; rollback allows any earlier stage; same-stage and leap-forwards are rejected with `InvalidTransition` → HTTP 403 code 40301.
- `stage_raw` is the English enum (frontend uses this for gating); `stage` Chinese label comes from `STAGE_ZH` and is display-only.
- Storyboard/character/scene write paths must call `assert_storyboard_editable` / `assert_asset_editable` before mutating rows.

**API envelope** — every response is `{"code": int, "message": str, "data": T|null}` via `app/api/envelope.py`. Errors are dispatched by `register_handlers` in `app/api/errors.py`:

| code  | HTTP | trigger                                             |
|-------|------|-----------------------------------------------------|
| 0     | 200  | success                                             |
| 40001 | 422  | `RequestValidationError` (and manual validation)    |
| 40301 | 403  | `InvalidTransition` (stage/job state machine)       |
| 40401 | 404  | `ProjectNotFound` and similar domain not-founds     |
| 42201 | 4xx  | content filter (Volcano moderation)                 |
| 50001 | 500  | uncaught `Exception` fallback                       |

Raise `ApiError(code, message, http_status)` from `app/api/errors.py` for controlled non-state-machine errors.

### Testing conventions

- `tests/conftest.py` wires the test MySQL via Alembic (not `Base.metadata.create_all`) so schema drift is caught. It uses `NullPool` to avoid the `Future attached to a different loop` error when session-scoped engines cross pytest-asyncio event loops.
- The `client` fixture rebinds `app.infra.db._engine` / `_session_factory` to the test engine, force-enables `celery_task_always_eager`, and **TRUNCATEs all tables after each test** for isolation.
- Missing `session.refresh(obj)` after insert can cause `MissingGreenlet` when accessing server-defaulted columns (e.g. `created_at`). See `ProjectService.create` as the reference pattern.
- HTTP stubs use `respx` (pinned); real Volcano integration tests live in `tests/integration/test_volcano_real_client.py` and require real `ARK_API_KEY`.

## Frontend (`frontend/`)

### Commands

```bash
cd frontend
npm install
npm run dev          # Vite dev on :5173, proxies /api and /static to 127.0.0.1:8000
npm run build        # runs vue-tsc --noEmit then vite build
npm run typecheck    # vue-tsc --noEmit only
npm run lint         # eslint on src/**/*.{ts,vue}
npm run format       # prettier on src/**/*.{ts,vue,css}
npm run test         # vitest run (happy-dom)
npm run test:watch
./scripts/smoke_m1.sh    # starts & tears down its own dev server; 5173 must be free
./scripts/smoke_m2.sh
```

### Architecture

Matches `frontend/frontend-stack-and-ux.md`. Key conventions:

- `src/api/` wraps Axios calls — no Pinia/store logic in here.
- `src/store/` is Pinia — cross-page state only; view-local state stays in the component.
- `src/composables/` hosts reusable logic. Two are load-bearing for stage/job semantics:
  - `useStageGate` — maps `stage_raw` to write-button enablement for each editor (storyboard/character/scene). The locked-stage toast offers a "回退阶段" shortcut that opens `StageRollbackModal`.
  - `useJobPolling` — polls `GET /api/v1/jobs/{id}` while a task is running.
- `src/views/` pages own flow/orchestration; `src/components/{layout,common,setup,storyboard,character,scene,generation,export,workflow}/` host business UI.
- `src/styles/` is the **only** place CSS variables/tokens live, migrated from `product/workbench-demo/`. Do not inline colors/sizes in components.
- Frontend `stage_raw` gating must stay in lock-step with backend `ProjectStageRaw`. Example: storyboard panel writes are only enabled for `draft` and `storyboard_ready`; a backend `40301` is shown as a toast with a rollback CTA.

## Cross-cutting rules

- The `AGENTS.md` at the repo root is intentionally empty. Do **not** assume agent instructions from it.
- When designing, prefer the MVP + mature-stack path in `docs/superpowers/specs/*`; stop asking for granular sign-offs on design sub-sections (project preference).
- Commits follow a milestone-task prefix pattern: `feat(backend): <summary>  (Task N)` — see `backend/README.md` bottom for the reference log. Keep one commit per plan task.
- Before claiming backend changes work, run the relevant `smoke_m*.sh`; they are end-to-end against a live stack. Tests alone do not cover the Celery + Volcano paths.
