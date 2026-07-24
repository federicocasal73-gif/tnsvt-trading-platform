# Reinicia todos los sistemas TNSVT V2
Write-Host "=== TNSVT V2 - Restart All ===" -ForegroundColor Cyan

# 1. Kill existing processes
Write-Host "[1/5] Matando procesos viejos..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Write-Host "  Done" -ForegroundColor Green

# 2. Start Bridge API (port 8522)
Write-Host "[2/5] Arrancando Bridge API (puerto 8522)..." -ForegroundColor Yellow
$bp = Start-Process -FilePath "python" -ArgumentList "E:\TNSVT-V2-Architecture\apps\bridge\bridge-api\main.py" -WindowStyle Hidden -PassThru
Write-Host "  PID: $($bp.Id)" -ForegroundColor Green
Start-Sleep -Seconds 5

# 3. Start Telegram Bot
Write-Host "[3/5] Arrancando Telegram Bot..." -ForegroundColor Yellow
$tp = Start-Process -FilePath "python" -ArgumentList "E:\TNSVT-V2-Architecture\apps\integrations\tnsvt-bot\bot\main.py" -WindowStyle Hidden -PassThru
Write-Host "  PID: $($tp.Id)" -ForegroundColor Green
Start-Sleep -Seconds 5

# 4. Start Frontend Vite (port 5180)
Write-Host "[4/5] Arrancando Frontend Vite (puerto 5180)..." -ForegroundColor Yellow
$fp = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "E:\TNSVT-V2-Architecture\apps\frontend" -WindowStyle Hidden -PassThru
Write-Host "  PID: $($fp.Id)" -ForegroundColor Green
Start-Sleep -Seconds 8

# 5. Verify
Write-Host "[5/5] Verificando servicios..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8522/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "  Bridge API: OK ($($r.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  Bridge API: ERROR ($($_.Exception.Message))" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Resumen ===" -ForegroundColor Cyan
Write-Host "Bridge API: http://localhost:8522"
Write-Host "Frontend:   http://localhost:5180"
Write-Host "Bot:        @terminalfinancieraproTNSVT_bot"
Write-Host ""
Write-Host "Para monitorear:"
Write-Host "  Get-Process -Name python, node"
Write-Host "=== FIN ===" -ForegroundColor Cyan
