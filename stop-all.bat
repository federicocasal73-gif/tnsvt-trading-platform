@echo off
title TNSVT MT5 Integration - Stopper
color 0C
echo ============================================================
echo    TNSVT V2 - Stopping Integrated Stack
echo ============================================================
echo.

echo [1/4] Cerrando Frontend Vite...
taskkill /FI "WINDOWTITLE eq TNSVT-Frontend*" /T /F >nul 2>&1

echo [2/4] Cerrando Gateway...
taskkill /FI "WINDOWTITLE eq TNSVT-Gateway*" /T /F >nul 2>&1
taskkill /IM api-gateway.exe /F >nul 2>&1

echo [3/4] Cerrando Auth Service...
taskkill /FI "WINDOWTITLE eq TNSVT-Auth*" /T /F >nul 2>&1
taskkill /IM auth-service.exe /F >nul 2>&1

echo [4/4] Cerrando Bridge API...
taskkill /FI "WINDOWTITLE eq TNSVT-Bridge*" /T /F >nul 2>&1
taskkill /IM python.exe /FI "WINDOWTITLE eq TNSVT-Bridge*" /T /F >nul 2>&1

echo.
echo [NOTA] D:\TradingBotMT5\START_BOT.bat NO se cierra aqui (es independiente)
echo        Para parar el bot MT5: cerrá la ventana negra de START_BOT.bat
echo.
echo Stack TNSVT detenido.
timeout /t 3
