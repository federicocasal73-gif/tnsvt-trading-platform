@echo off
title TNSVT V2 - MT5 Snapshot Worker
color 0E
cd /d "D:\TradingBotMT5"

echo ============================================
echo  MT5 SNAPSHOT WORKER (puente entre MT5 y bridge-api)
echo ============================================
echo  Escribe account_snapshot.json cada 3s a:
echo    %CD%\account_snapshot.json
echo    %CD%\positions_snapshot.json
echo  El bridge-api :8522 los lee y los expone.
echo.

"C:\Users\HP 240 inch G9\AppData\Local\Programs\Python\Python312\python.exe" mt5_snapshot_worker.py
pause
