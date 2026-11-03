# Backend V2

API inicial de FastAPI para la arquitectura local-first híbrida.

## Desarrollo local

Requiere Python 3.12 o superior.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

La API expone:
- `GET /health`: liveness.
- `GET /api/v1/system/info`: versión y modo de arquitectura.
- `/docs`: documentación OpenAPI.

## Docker

Desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env
# Edita .env y sustituye POSTGRES_PASSWORD.
docker compose up --build -d
```

Esta base todavía no implementa autenticación, ventas ni sincronización. No exponer el puerto de API a Internet ni usar credenciales de ejemplo en producción.
