@echo off
REM ============================================
REM   BRIDGE API Python - DESHABILITADO
REM ============================================
REM   El bridge FastAPI Python (api_server.py,
REM   puerto 8502) fue reemplazado por el
REM   apps/bridge/bridge-api/ dentro del monorepo
REM   TNSVT V2 (E:\TNSVT-V2-Architecture).
REM
REM   Ese bridge unificado expone:
REM     - MT5 /api/v1/bridge/mt5/*
REM     - Analytics /api/v1/bridge/analytics/*
REM     - Telegram /api/v1/bridge/telegram/*
REM     - Control /api/v1/bridge/control/*
REM ============================================

echo.
echo ============================================
echo   BRIDGE API Python DESHABILITADO
echo ============================================
echo.
echo   Esta version del bridge (puerto 8502) ya
echo   no se utiliza.  El bridge unificado vive
REM   en E:\TNSVT-V2-Architecture\apps\bridge\bridge-api
REM   y se sirve detras del API Gateway en
REM   http://localhost:8000.
echo.
echo   Si necesitas reiniciarlo (solo debug):
REM     cd /d "%~dp0"
REM     python api_server.py
echo.
pause
