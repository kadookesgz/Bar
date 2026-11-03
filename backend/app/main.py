from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.db import engine
from app.models import Base
from app.routers import (
    auth, cash, catalog, customers, employee_shifts, employees, floor, inventory, kitchen,
    management, menus, online, orders, pricing, promotions, purchases, recipes, reports, reservations, setup, venues,
)

settings = get_settings()
if settings.environment.lower() in {"production", "prod"} and (len(settings.jwt_secret) < 48 or "DEV_ONLY" in settings.jwt_secret or "CAMBIAR" in settings.jwt_secret):
    raise RuntimeError("JWT_SECRET debe ser un secreto aleatorio de al menos 48 caracteres en producción.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conveniencia únicamente para desarrollo local. Producción usa Alembic.
    if settings.environment == "development":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API local-first para TPV de hostelería multiempresa.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

for router in (
    setup.router, auth.router, cash.router, kitchen.router, employee_shifts.router, reservations.router,
    inventory.router, employees.router, online.router, catalog.router, floor.router,
    orders.router, management.router, reports.router, customers.router, menus.router, pricing.router, promotions.router, purchases.router, recipes.router, venues.router,
):
    app.include_router(router)


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
        "modules": "auth,catalog,floor,orders,kitchen,cash,reservations,inventory,employees,customers,reports,qr",
    }


@app.get("/", include_in_schema=False)
async def pos_app():
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "index.html")


@app.get("/qr/{token}", include_in_schema=False)
async def public_qr_app(token: str):
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "qr.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest():
    return FileResponse(
        Path(__file__).resolve().parents[2] / "frontend" / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/extensions.js", include_in_schema=False)
async def ui_extensions():
    return FileResponse(
        Path(__file__).resolve().parents[2] / "frontend" / "extensions.js",
        media_type="application/javascript",
    )


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        Path(__file__).resolve().parents[2] / "frontend" / "sw.js",
        media_type="application/javascript",
    )
