@echo off
title TNSVT V2 - Bridge API (FastAPI)
color 0B
cd /d "E:\TNSVT-V2-Architecture\apps\bridge\bridge-api"

REM Cargar venv si existe; si no usar python global
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    set PY=python.exe
)

echo Iniciando Bridge API en puerto 8522...
echo Endpoints principales:
echo   GET  /health
echo   POST /api/v1/bridge/mt5/order
echo   POST /api/v1/bridge/copier/trades
echo   GET  /api/v1/bridge/copier/dashboard
echo Docs: http://localhost:8522/docs
echo.

%PY% -m uvicorn main:app --host 0.0.0.0 --port 8522 --log-level info
pause
