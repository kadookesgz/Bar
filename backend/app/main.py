from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import engine
from app.models import Base  # Importa todos los modelos para registrar el metadata.
from app.routers import auth, catalog, floor, management, orders, setup

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conveniencia únicamente para desarrollo local. Producción debe usar Alembic.
    if settings.environment == "development":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API local-first para TPV de hosteleria multiempresa. "
        "Incluye catálogo, sala, comandas y cola de cocina."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID", "X-Venue-ID"],
)

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(floor.router)
app.include_router(orders.router)
app.include_router(management.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tpv-api"}


@app.get("/api/v1/system/info", tags=["system"])
async def system_info() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "architecture": "local-first-hybrid",
        "modules": "catalog,floor,orders,kitchen,management",
    }
