$base = "E:\TNSVT-V2-Architecture"

# Environment
$env:REDIS_HOST = "localhost"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_USER = "tnsvt"
$env:POSTGRES_DB = "tnsvt"
$env:JWT_SECRET = "dev-jwt-secret-change-me"
$env:AUTH_JWT_SECRET = "dev-jwt-secret-change-me"
$env:SIGNAL_INGEST_API_KEY = "dev-ingest-key"
$env:TELEGRAM_BOT_TOKEN = "test:dummy-token-for-dev"

# Start all services
$svcs = @(
    @{Name="auth-service";       Dir="apps\platform\auth-service";          Port=8001},
    @{Name="user-service";       Dir="apps\platform\user-service";          Port=8401},
    @{Name="signal-engine";      Dir="apps\trading\signal-engine";          Port=8003},
    @{Name="copy-trading";       Dir="apps\trading\copy-trading";           Port=8005},
    @{Name="telegram-bot-service";Dir="apps\notification\telegram-bot-service";Port=8503},
    @{Name="api-gateway";        Dir="apps\gateway\api-gateway";            Port=8000}
)

# Kill old instances
Get-Process -Name "auth-service","user-service","signal-engine","copy-trading","telegram-bot-service","api-gateway" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

foreach ($svc in $svcs) {
    $exe = "$base\$($svc.Dir)\$($svc.Name).exe"
    if (Test-Path $exe) {
        Start-Process -NoNewWindow -FilePath $exe -RedirectStandardOutput "$base\$($svc.Dir)\svc.log" -RedirectStandardError "$base\$($svc.Dir)\svc.err"
        Write-Host "Started $($svc.Name) on port $($svc.Port)"
        Start-Sleep -Seconds 2
    } else {
        Write-Host "Binary not found: $exe"
    }
}

Write-Host ""
Write-Host "=== Services Running ==="
Get-Process -Name "auth-service","user-service","signal-engine","copy-trading","telegram-bot-service","api-gateway" -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, @{N="Port";E={($_|Get-Process).Id}} | Format-Table -AutoSize
