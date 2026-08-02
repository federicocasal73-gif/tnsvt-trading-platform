$env:JWT_SECRET = "zFLSkEfUYNpA9vT1tQAAwOGPgwvdJ3PR3wasfxe7KM7O2RQXPyHEVQgqeJXsW7Pg"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "tnsvt"
$env:POSTGRES_USER = "tnsvt"
$env:POSTGRES_PASSWORD = "tnsvt"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:ACCOUNT_MANAGER_PORT = "8510"
$env:MT5_PASSWORD_KEY = "f1eeb48656dbfde112294b04f8a35579839ed9115844a50fa52824d7c2e468b7"
$env:ACCOUNT_MGR_SERVICE_TOKEN = "40f83dcafb0a9e3b07e002cf9b176d3db9d2d42407bb8ad2d8b234768a7ae930"
$env:ENV = "development"
$env:LOG_LEVEL = "info"

Get-Process -Name "account-manager" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Set-Location "E:\TNSVT-V2-Architecture\bin"
$proc = Start-Process -FilePath ".\account-manager.exe" `
    -RedirectStandardOutput "E:\TNSVT-V2-Architecture\logs\account-manager.log" `
    -RedirectStandardError "E:\TNSVT-V2-Architecture\logs\account-manager.log.err" `
    -PassThru -WindowStyle Hidden

Write-Host "account-manager PID: $($proc.Id)"
Start-Sleep -Seconds 4
$ready = Test-NetConnection -ComputerName 127.0.0.1 -Port 8510 -InformationLevel Quiet
Write-Host "8510 listening: $ready"
