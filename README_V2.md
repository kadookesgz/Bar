# TPV Hostelería — V2 híbrida

La rama `v2-hybrid-architecture` inicia la evolución de la aplicación QR V1 hacia un TPV multiempresa, multiplataforma y local-first.

## Estado

- Documentación de arquitectura y roadmap: `docs/`.
- API base FastAPI: `backend/`.
- PostgreSQL local y API en Docker Compose.
- La V1 continúa disponible en `main`; esta rama no la sustituye todavía.

## Arranque de la base técnica

Requisitos: Docker Desktop con Docker Compose.

En PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
# Sustituye POSTGRES_PASSWORD por un secreto largo y único.
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/v1/system/info
```

Documentación OpenAPI: http://localhost:8000/docs

## Importante

Este commit es un esqueleto técnico, no un TPV operativo. Todavía no implementa autenticación, productos, mesas, ventas, caja, cocina, impresión ni sincronización. No exponerlo a Internet ni usarlo en producción.

## Próximo trabajo

1. Migraciones Alembic y modelo Tenant/Venue/User.
2. Autenticación, sesiones, roles y aislamiento multiempresa.
3. Catálogo y mesas.
4. Comandas y caja con transacciones y auditoría.
5. KDS y PWA.
6. Motor de sincronización local-nube.
