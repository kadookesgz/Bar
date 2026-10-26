#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo 'Edita .env, cambia ADMIN_PASSWORD y pon BASE_URL con la IP del equipo.'
echo 'Después ejecuta: set -a; source .env; set +a; source .venv/bin/activate; uvicorn app:app --host 0.0.0.0 --port 8000'
