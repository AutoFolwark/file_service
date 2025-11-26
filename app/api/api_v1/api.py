from fastapi import APIRouter

from app.api.api_v1.endpoints.public.files import files_router

public_v1_router = APIRouter(prefix='/v1/public')
private_v1_router = APIRouter(prefix='/private/v1')

public_v1_router.include_router(files_router)





