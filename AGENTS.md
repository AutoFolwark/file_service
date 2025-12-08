# Repository Guidelines

## Project Structure & Module Organization
- `app/main.py` boots the FastAPI app; `app/core/` holds the app factory, logging, and shared utilities.
- `app/routers/` exposes HTTP routes; pair request/response models in `app/schemas/` and domain enums in `app/enums/`.
- Persistence and integrations live in `app/database/`, `app/services/`, `app/tasks/` (Celery), and `app/rpc_client/`.
- Alembic migrations reside in `alembic/` with settings in `alembic.ini`. Runtime configuration is read from `.env` in the repo root via `app/config.py`.

## Build, Test, and Development Commands
- Install deps (no venv inside container): `poetry install`.
- Run the API locally with reload: `poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
- Apply migrations (DB env vars required): `poetry run alembic upgrade head`.
- Smoke tests (Pytest): `poetry run pytest`.
- Container build/run: `docker build -t files-service .` then `docker run --env-file .env -p 8000:8000 files-service`.

## Coding Style & Naming Conventions
- Python 3.13+, PEP 8, 4-space indents, and type hints on public functions. Prefer FastAPI/Pydantic models for IO boundaries.
- Module layout: keep request handlers thin in `routers/`; push logic into `services/`; isolate persistence in `database/` and async tasks in `tasks/`.
- Use `loguru` via `app/core/logger.py`; emit structured context rather than print statements.
- Name migrations descriptively (e.g., `alembic revision -m "add_file_status_enum"`). Keep schema changes idempotent.

## Testing Guidelines
- Tests use Pytest; place files under a top-level `tests/` directory named `test_*.py`.
- Write API tests against FastAPI’s test client; mock external services (S3, RPC, RabbitMQ) to keep runs deterministic.
- Target high coverage for routers, services, and task logic before merging significant changes.
- Run `poetry run pytest` locally; prefer small, focused fixtures over shared global state.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (e.g., `add presigned url endpoint`, `adjust celery schedule`). Keep one concern per commit.
- PRs should describe motivation, main changes, and any operational notes (migrations, new env vars, breaking API tweaks). Link issues if applicable.
- Include screenshots or curl examples when altering endpoints or response shapes. Mention how to test locally (commands/env needed).

## Configuration & Security Tips
- Required env keys: database (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`), RabbitMQ (`RABBITMQ_URL`, `RABBITMQ_EXCHANGE_NAME`), and S3 credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, etc.). Never commit real secrets.
- Default docs (`/docs`, `/redoc`) only expose in development; ensure `ENVIRONMENT=production` in deployed settings.
