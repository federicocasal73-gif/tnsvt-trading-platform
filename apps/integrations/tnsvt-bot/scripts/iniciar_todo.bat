@echo off
title TERMINAL FINANCIERA PRO - MODO COMPLETO
color 0A

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║    TERMINAL FINANCIERA PRO - INICIO COMPLETO     ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Servicios que se iniciaran:
echo    1. TNSVT Symfony (Web + APK)
echo    2. Signal Copier (Telethon + MT5)
echo    3. Dashboard Streamlit
echo    4. Bridge API (FastAPI)
echo    5. Bot Telegram
echo.
echo  IMPORTANTE: MT5 debe estar abierto con Algo Trading ON
echo.

set /p confirm="Iniciar todo? (S/N): "
if /i not "%confirm%"=="S" (
    echo Cancelado.
    pause
    exit /b 0
)

cd /d "%~dp0"

echo.
echo ─────────────────────────────────────────────────
echo  [1/5] TNSVT Symfony (Web)
echo ─────────────────────────────────────────────────
start "TNSVT Symfony" cmd /c "cd /d C:\Users\HP 240 inch G9\Documents\TNSVT-WORK\tnsvt-symfony && php -S 0.0.0.0:8000 -t public"
timeout /t 2 /nobreak > nul

echo ─────────────────────────────────────────────────
echo  [2/5] Signal Copier
echo ─────────────────────────────────────────────────
start "Signal Copier" cmd /c "python -m signal_copier.main"
timeout /t 3 /nobreak > nul

echo ─────────────────────────────────────────────────
echo  [3/5] Dashboard Streamlit
echo ─────────────────────────────────────────────────
start "Dashboard" cmd /c "streamlit run dashboard/app.py --server.port 8501"
timeout /t 3 /nobreak > nul

echo ─────────────────────────────────────────────────
echo  [4/5] Bridge API (FastAPI)
echo ─────────────────────────────────────────────────
start "Bridge API" cmd /c "python api_server.py"
timeout /t 2 /nobreak > nul

echo ─────────────────────────────────────────────────
echo  [5/5] Bot Telegram
echo ─────────────────────────────────────────────────
start "Bot Telegram" cmd /c "python -m bot.main"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║         TODOS LOS SERVICIOS INICIADOS            ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Servicio           URL / Estado
echo  ─────────────────────────────────────────
echo  TNSVT Web          https://laptop-ebgqig6j.tailf43f87.ts.net
echo  Signal Copier      Activo (MT5)
echo  Dashboard          http://localhost:8501
echo  Bridge API         http://localhost:8502
echo  Bot Telegram       @terminalfinancieraproTNSVT_bot
echo.
echo  Para detener todo: detener_todo.bat
echo.

pause
