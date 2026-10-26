@echo off
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Edita .env antes del primer uso para cambiar ADMIN_PASSWORD y configurar BASE_URL.
echo Cuando lo hayas configurado, el servidor se iniciara ahora.
uvicorn app:app --host 0.0.0.0 --port 8000
pause
