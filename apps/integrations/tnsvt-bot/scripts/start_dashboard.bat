@echo off
REM ============================================
REM   STREAMLIT DASHBOARD - DESHABILITADO
REM ============================================
REM   El dashboard de Streamlit fue reemplazado
REM   por el frontend Vite + React del monorepo
REM   TNSVT V2 (E:\TNSVT-V2-Architecture).
REM
REM   Acceso al dashboard unificado:
REM     - Frontend Vite: http://localhost:5180
REM
REM   Paginas relevantes:
REM     - /history        (historial de trades)
REM     - /mt5-dashboard  (cuenta/balance MT5)
REM     - /mt5-positions  (posiciones abiertas)
REM     - /mt5-channels   (canales Telegram)
REM     - /mt5-control    (start/stop del bot)
REM ============================================

echo.
echo ============================================
echo   DASHBOARD DESHABILITADO
echo ============================================
echo.
echo   El dashboard Streamlit (puerto 8501) fue
echo   reemplazado por el frontend Vite unificado:
echo.
echo      http://localhost:5180
echo.
echo   Si necesitas reiniciarlo:
REM     cd /d "%~dp0"
REM     streamlit run dashboard/app.py --server.port 8501
echo.
pause
