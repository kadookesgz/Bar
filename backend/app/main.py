from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import engine
from app.models import Base  # Importa todos los modelos para registrar el metadata.
from app.routers import auth, cash, catalog, employees, floor, inventory, kitchen, management, online, orders, reservations, setup

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
app.include_router(cash.router)
app.include_router(kitchen.router)
app.include_router(reservations.router)
app.include_router(inventory.router)
app.include_router(employees.router)
app.include_router(online.router)
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


@app.get("/", include_in_schema=False)
async def pos_app():
    ui_path = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    return FileResponse(ui_path)


@app.get("/qr/{token}", include_in_schema=False)\nasync def public_qr_app(token: str):\n    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "qr.html")\n\n\n@app.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest():
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/extensions.js", include_in_schema=False)\nasync def ui_extensions():\n    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "extensions.js", media_type="application/javascript")\n\n\n@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "sw.js", media_type="application/javascript")
