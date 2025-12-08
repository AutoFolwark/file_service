# Vinas Files Service

FastAPI-based file and image service that issues presigned S3 URLs for uploads and downloads, stores metadata in Postgres/SQLite via SQLAlchemy, and exposes endpoints for listing and status updates.

## Celery

- Run worker: `poetry run celery -A app.celery_app.celery_app worker --loglevel=info`
- Run beat (uses in-code 60s schedule for `sync_pending_uploads`): `poetry run celery -A app.celery_app.celery_app beat --loglevel=debug --scheduler=celery.beat:Scheduler`
