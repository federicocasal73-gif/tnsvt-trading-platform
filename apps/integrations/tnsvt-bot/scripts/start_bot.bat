@echo off
title MT5 Trading Bot - Launcher
echo ----------------------------------------------------
echo         INICIANDO SISTEMA DE TRADING INTEGRAL
echo ----------------------------------------------------
echo.
echo [1/3] Verificando entorno...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    pause
    exit
)

echo [2/3] Limpiando estados anteriores...
if exist bot_state.json del bot_state.json

echo [3/3] Ejecutando Orquestador (Main)...
echo.
echo NOTA: Se abrira el navegador automaticamente.
echo NO CIERRES ESTA VENTANA NEGRA.
echo.
python main.py
pause
