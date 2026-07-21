@echo off
title TERMINAL FINANCIERA PRO - Detener Todos
color 0C

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║         DETENIENDO TODOS LOS SERVICIOS           ║
echo  ╚══════════════════════════════════════════════════╝
echo.

echo  [1/6] Deteniendo TNSVT Symfony...
taskkill /FI "WINDOWTITLE eq TNSVT Symfony*" /F >nul 2>&1

echo  [2/6] Deteniendo Signal Copier...
taskkill /FI "WINDOWTITLE eq Signal Copier*" /F >nul 2>&1

echo  [3/6] Deteniendo Dashboard...
taskkill /FI "WINDOWTITLE eq Dashboard*" /F >nul 2>&1

echo  [4/6] Deteniendo Bridge API...
taskkill /FI "WINDOWTITLE eq Bridge API*" /F >nul 2>&1

echo  [5/6] Deteniendo Bot Telegram...
taskkill /FI "WINDOWTITLE eq Bot Telegram*" /F >nul 2>&1

echo  [6/6] Limpiando procesos PHP sobrantes...
taskkill /IM php.exe /F >nul 2>&1

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║        TODOS LOS SERVICIOS DETENIDOS             ║
echo  ╚══════════════════════════════════════════════════╝
echo.
pause
