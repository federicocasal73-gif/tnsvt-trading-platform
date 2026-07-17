@echo off
title TNSVT MT5 Integration - Lanzador Unificado
color 0B
echo ============================================================
echo    TNSVT V2 - Integrated Stack
echo ============================================================
echo.
echo [Puertos:]
echo   Frontend  TNSVT  :5180
echo   Gateway   TNSVT  :8000
echo   Auth      TNSVT  :8001
echo   Bridge    TNSVT  :8522 (NUEVO)
echo   MT5 Bot   native :8501 (Streamlit)
echo.
echo ============================================================
echo.

REM ─── 1. Verificar Python ───
echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado
    pause
    exit /b 1
)

REM ─── 2. Arrancar Bridge API :8522 ───
echo [2/5] Arrancando Bridge API :8522...
set "BRIDGE_DIR=%~dp0apps\bridge\bridge-api"
if exist "%BRIDGE_DIR%\.venv\Scripts\python.exe" (
    start "TNSVT-Bridge" /min cmd /c "cd /d %BRIDGE_DIR% && .venv\Scripts\python.exe main.py"
) else (
    start "TNSVT-Bridge" /min cmd /c "cd /d %BRIDGE_DIR% && python -m venv .venv && .venv\Scripts\activate.bat && pip install -q -r requirements.txt && python main.py"
)
timeout /t 3 >nul

REM ─── 3. Arrancar Auth Service ───
echo [3/5] Arrancando Auth Service :8001...
if exist "C:\Users\HP 240 inch G9\AppData\Local\Temp\opencode\auth-service.exe" (
    start "TNSVT-Auth" /min cmd /c "C:\Users\HP 240 inch G9\AppData\Local\Temp\opencode\auth-service.exe"
) else (
    echo [WARN] auth-service.exe no encontrado, compilar primero
)

REM ─── 4. Arrancar API Gateway ───
echo [4/5] Arrancando API Gateway :8000...
start "TNSVT-Gateway" /min cmd /c "C:\Users\HP 240 inch G9\AppData\Local\Temp\opencode\api-gateway.exe"

REM ─── 5. Arrancar Frontend :5180 ───
echo [5/5] Arrancando Frontend Vite :5180...
cd /d "%~dp0apps\frontend"
if not exist node_modules (
    echo [INFO] Instalando dependencias npm...
    call npm install
)
start "TNSVT-Frontend" /min cmd /c "npm run dev"

echo.
echo ============================================================
echo    Stack completo levantado
echo ============================================================
echo.
echo   Frontend:  http://localhost:5180
echo   Gateway:   http://localhost:8000
echo   Bridge:    http://localhost:8522/docs
echo   MT5 Bot:   http://localhost:8501 (D:\TradingBotMT5\START_BOT.bat)
echo.
echo    Login: admin@tnsvt.local / Admin123!Demo
echo ============================================================
echo.
timeout /t 5
start http://localhost:5180
pause
