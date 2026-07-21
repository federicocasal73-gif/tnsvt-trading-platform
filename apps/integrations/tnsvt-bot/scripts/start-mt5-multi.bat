@echo off
title TNSVT V2 - MT5 Multi-Cuenta Snapshot Worker
color 0E
cd /d "D:\TradingBotMT5"

echo ============================================
echo  MT5 MULTI-CUENTA SNAPSHOT WORKER
echo  Lee accounts.json y escribe snapshot por login
echo  (account_snapshot_<login>.json, positions_snapshot_<login>.json)
echo  Tambien mantiene archivos legacy account_snapshot.json
echo  y positions_snapshot.json (la cuenta demo_main).
echo ============================================
echo.

"C:\Users\HP 240 inch G9\AppData\Local\Programs\Python\Python312\python.exe" -u mt5_multi_snapshot.py
pause
