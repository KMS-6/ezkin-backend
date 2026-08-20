# EZkin Backend — Copilot Instructions

FastAPI backend providing non-medical, lifestyle/environment-based skin care reference info.
It explicitly does not provide medical diagnosis or treatment.

## Commands

```bash
uv sync --frozen                          # install deps (uses uv.lock, do not upgrade ad hoc)
docker compose up -d db                   # local PostgreSQL only
uv run alembic upgrade head                # apply migrations
uv run uvicorn app.main:app --reload       # dev server (http://localhost:8000, /docs for Swagger)

uv run ruff format --check .               # format check (CI-enforced)
uv run ruff check .                        # lint (CI-enforced)
uv run pytest                              # full test suite (SQLite in-memory, no DB needed)
uv run pytest tests/test_shelf_api.py::test_user_can_manage_own_shelf_product  # single test
uv run pytest tests/test_shelf_api.py -k "create"                       # by keyword

docker compose config --quiet && docker build -t ezkin-api:local .   # pre-push deploy sanity check
```

Tests never need `docker compose up db` — they spin up an isolated in-memory SQLite engine per test
(see `tests/conftest.py`) and never touch the dev Postgres instance.

## Architecture

- **Layout**: `app/models/` (SQLAlchemy ORM) → `app/modules/<name>/{schemas.py,router.py}` (one
  package per domain) → registered in `app/api/router.py`. Adding an endpoint touches all three,
  plus an Alembic migration if the model changed.
- **Two separate identity/auth mechanisms coexist — do not mix them up**:
  - **Real users** (`users`, `shelf` modules): `POST /api/v1/users` registers a user and returns an
    HMAC-signed access token (`app/core/auth.py`, see `docs/decisions/001-signed-user-token.md`).
    Protected routes depend on `get_current_user_id` and expect `Authorization: Bearer <token>`.
    `X-User-Id` is *not* trusted as auth (it was, and got fixed — see ADR 001).
  - **Mock personas** (most other domain modules: `scans`, `reports`, `onboarding`, `risk`,
    `briefings`, `recommendations`, `feedback`, `health_metrics`, `cosmetics_catalog`, `triggers`):
    identified purely by the `X-Mock-Persona-Id` header resolved against the `personas` table via
    `app/core/mock_persona.get_persona_id` (re-exported from `app/core/persona.py`). There is no
    login for personas — `persona_001`/`persona_002`/`persona_003` are seeded directly by the
    `20260816_0002` Alembic migration's `op.bulk_insert`, not by application code or a seed script.
  - Admin-only endpoints depend on `require_admin`/`get_admin` (`X-Admin-Key`), partner-only
    endpoints on `app/core/partner_auth.py` (`X-Partner-Key`). All three secrets
    (`AAC_AUTH_SECRET`, `AAC_ADMIN_API_KEY`, `AAC_PARTNER_API_KEY`) are required, non-default
    `SecretStr` settings — the app fails to start without them (see `app/core/config.py`).
- **Config**: `pydantic-settings` with `AAC_` env prefix (`app/core/config.py`), loaded from `.env`.
  `AAC_CORS_ORIGINS` must be a JSON array, not a comma-separated string.
- **Migrations run inside the FastAPI container/entrypoint** (`alembic upgrade head` before
  `uvicorn` starts). `alembic/env.py` wraps the run in a Postgres advisory lock
  (`hashtext('ezkin_alembic_migration')`) to serialize concurrent deploys — the lock query opens an
  implicit transaction, so an explicit `await connection.commit()` after `run_sync` is required or
  the whole migration silently rolls back while still exiting 0. Keep that commit if you touch
  `env.py`.
- **Idempotency**: write endpoints that must tolerate client retries persist request hashes via
  `app/core/idempotency.py` / `IdempotencyRecord`, keyed by `(scope, subject, key)`; replays return
  the stored response, mismatched payloads for the same key raise 409.
- **Admin writes** are recorded via `app/models/audit_log.py`.
- **Optional LLM features degrade silently**: if `AAC_OPENAI_API_KEY` is unset, chat LLM
  escalation and Vision scan analysis fall back to rule-based / `model_not_implemented` behavior
  instead of erroring (see comments in `app/core/config.py`). LLM provider is OpenAI (see
  `docs/decisions/003-switch-llm-provider-to-openai.md`).
- **Deploy**: Render Blueprint (`render.yaml`) provisions `ezkin-api` (Docker) + `ezkin-db`
  (managed Postgres). CI (`.github/workflows/ci.yml`) triggers the Render deploy hook on push to
  `main` after the `backend` and `deployment-config` jobs pass — note `render.yaml` itself still
  pins `branch: develop`, so keep `develop` and `main` in sync or this will diverge. Full procedure
  in `docs/deployment.md`.

## Conventions

- **Soft delete**: `deleted_at` timestamp + `is_active` boolean flag, never a hard delete (see
  `Cosmetic` model / `shelf` router).
- **DB session**: always `Annotated[AsyncSession, Depends(get_db)]`, never construct a session
  directly in a router.
- **New model checklist**: add to `app/models/<name>.py` **and** register it in
  `app/models/__init__.py` (Alembic autogenerate only sees registered models), then
  `uv run alembic revision --autogenerate -m "설명"` and check the generated diff by hand.
- **Branching/PR workflow** is process, not code, but affects where fixes land:
  `feature/be/* → develop → main`; PRs require a linked Issue (`Related to #N` /
  `Closes #N`), `[Type] summary` titles (`Feature`/`Fix`/`Refactor`/`Docs`/`Test`/`Chore`), and an
  "AI 사용 여부" section disclosing AI involvement (`docs/conventions/code-review.md`,
  `docs/conventions/github-workflow.md`).
- **ADRs** for hard-to-reverse decisions live in `docs/decisions/NNN-title.md`.
- Commit messages, PR descriptions, and code comments in this repo are written in Korean.
