@echo off
title Terminal Financiera Pro - Copiador de Senales
color 0B

echo ============================================
echo   TERMINAL FINANCIERA PRO - COPIADOR
echo ============================================
echo.

cd /d "%~dp0"

echo [INFO] Verificando entorno...
if not exist ".env" (
    echo [ERROR] Archivo .env no encontrado
    pause
    exit /b 1
)

echo [INFO] Verificando MetaTrader 5...
echo [IMPORTANTE] Asegurate de que MT5 este abierto y con AlgoTrading activado
echo.

set /p confirm="Continuar? (S/N): "
if /i not "%confirm%"=="S" (
    echo Operacion cancelada
    pause
    exit /b 0
)

echo [INFO] Iniciando Copiador de Senales...
echo.

python -m signal_copier.main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] El copiador se detuvo con errores
    echo Revisa el archivo signal_copier.log para mas detalles
)

pause
