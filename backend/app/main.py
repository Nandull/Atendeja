from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    clients,
    health,
    me,
    members,
    professionals,
    services,
    time_blocks,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API do AtendeJá. Documentação interativa em /docs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(auth.router)
api.include_router(me.router)
api.include_router(members.router)
api.include_router(services.router)
api.include_router(professionals.router)
api.include_router(time_blocks.router)
api.include_router(clients.router)

app.include_router(health.router)
app.include_router(api)
