from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API local-first para TPV de hosteleria multiempresa. "
        "La operativa de venta se ejecutara en el nodo local."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe: confirms that the API process is responding."""
    return {"status": "ok", "service": "tpv-api"}


@app.get("/api/v1/system/info", tags=["system"])
async def system_info() -> dict[str, str]:
    """Non-sensitive build information for the local administration screen."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "architecture": "local-first-hybrid",
    }
