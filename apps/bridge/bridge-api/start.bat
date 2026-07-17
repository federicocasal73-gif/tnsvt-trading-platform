@echo off
title TNSVT Bridge API
echo ============================================================
echo    TNSVT Bridge API - :8502
echo    Bridge D:\TradingBotMT5 \-\-> TNSVT
echo ============================================================
echo.

cd /d "%~dp0"

if not exist .venv (
    echo [1/3] Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python no encontrado en PATH
        pause
        exit /b 1
    )
)

echo [2/3] Instalando dependencias...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install fallo
    pause
    exit /b 1
)

echo [3/3] Iniciando Bridge API en :8502...
echo.
python main.py
