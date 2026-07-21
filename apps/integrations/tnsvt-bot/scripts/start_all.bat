@echo off
title Terminal Financiera Pro - Todos los Servicios
color 0C

echo ============================================
echo   TERMINAL FINANCIERA PRO - MODO COMPLETO
echo ============================================
echo.
echo Este script inicia todos los servicios:
echo   1. Bot de Telegram
echo   2. Copiador de Senales
echo   3. Dashboard Streamlit
echo   4. TNSVT Bridge (FastAPI)
echo.
echo IMPORTANTE: Asegurate de que MT5 este abierto
echo             y con "Algo Trading" habilitado
echo.

cd /d "%~dp0"

set /p confirm="Iniciar todos los servicios? (S/N): "
if /i not "%confirm%"=="S" (
    echo Operacion cancelada
    pause
    exit /b 0
)

echo.
echo [1/4] Iniciando Bot de Telegram...
start "Bot Telegram" cmd /c "python -m bot.main"

timeout /t 3 /nobreak > nul

echo [2/4] Iniciando Copiador de Senales...
start "Copiador" cmd /c "python -m signal_copier.main"

timeout /t 3 /nobreak > nul

echo [3/4] Iniciando Dashboard...
start "Dashboard" cmd /c "streamlit run dashboard/app.py --server.port 8501"

timeout /t 3 /nobreak > nul

echo [4/4] Iniciando TNSVT Bridge...
start "TNSVT Bridge" cmd /c "python api_server.py"

echo.
echo ============================================
echo   TODOS LOS SERVICIOS INICIADOS
echo ============================================
echo.
echo Bot Telegram:    @terminalfinancieraproTNSVT_bot
echo Copiador:        Activo (MT5)
echo Dashboard:       http://localhost:8501
echo TNSVT Bridge:    http://localhost:8502
echo TNSVT Web:       https://laptop-ebgqig6j.tailf43f87.ts.net
echo.
echo Para detener, cierra las ventanas de cada servicio
echo o ejecuta: detener_todo.bat
echo.

pause
