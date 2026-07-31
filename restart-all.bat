@echo off
cd /d "E:\TNSVT-V2-Architecture"
for /f "usebackq delims=" %%a in (".env") do (
    for /f "tokens=1,* delims==" %%b in ("%%a") do (
        if not "%%b"=="" if not "%%b"=="#" set "%%b=%%c"
    )
)echo Starting Go services...
start /B apps\platform\auth-service\service.exe
start /B apps\gateway\api-gateway\service.exe
start /B apps\platform\account-manager\service.exe
start /B apps\trading\signal-engine\service.exe
start /B apps\trading\copy-trading\service.exe
start /B apps\trading\execution-engine\service.exe
start /B apps\risk\risk-engine\service.exe
start /B apps\ai\signal-generator\service.exe
start /B apps\market-data\price-feed\service.exe
start /B apps\notification\telegram-bot-service\service.exe
echo Starting Python services...
start /B /D apps\bridge\bridge-api .venv\Scripts\python main.py
start /B /D apps\ai\orchestrator .venv\Scripts\python -m app.main
start /B /D apps\ai\news-analyzer python app\main.py
echo All 13 services started.
