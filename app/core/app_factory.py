from contextlib import asynccontextmanager
from typing import Callable, Optional

from fastapi import FastAPI
from fastapi_problem.handler import add_exception_handler, new_exception_handler

from app.config import settings
from app.core.logger import logger


def setup_middleware_and_handlers(app: FastAPI):
    eh = new_exception_handler()
    add_exception_handler(app, eh)


def create_app(
        lifespan_override: Optional[Callable] = None
) -> FastAPI:
    @asynccontextmanager
    async def default_lifespan(_: FastAPI):
        logger.info(
            "Application startup complete",
            app=settings.APP_NAME,
            environment=settings.ENVIRONMENT,
            docs_enabled=settings.enable_docs,
        )
        yield


    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None

    app = FastAPI(
        title="Files Service",
        description="Manages all files and images",
        version="0.0.1",
        root_path=settings.ROOT_PATH,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan_override or default_lifespan
    )

    setup_middleware_and_handlers(app)
    return app
