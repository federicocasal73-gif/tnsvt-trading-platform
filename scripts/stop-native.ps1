# TNSVT V2 — stop nativo de servicios
# Detiene todos los procesos Go y Python del stack TNSVT, conserva postgres/redis/nats si estan como servicios Windows.

$repo = "E:\TNSVT-V2-Architecture"
$pidDir = Join-Path $repo "run"

$names = @(
    "account-manager", "auth-service", "signal-engine", "risk-engine",
    "execution-engine", "copy-trading", "orchestrator", "liquidity-engine", "news-analyzer",
    "macro-fetcher", "news-bridge", "mt5-connector", "api-gateway",
    "audit-engine"
)

Write-Host "=== TNSVT V2 stop nativo ===" -ForegroundColor Cyan

$stopped = 0
$notFound = 0

# Detener via PID files primero
foreach ($name in $names) {
    $pidFile = Join-Path $pidDir "$name.pid"
    if (Test-Path $pidFile) {
        $savedPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($savedPid -and ($savedPid -match '^\d+$')) {
            $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  stopping $name (PID=$savedPid)..."
                Stop-Process -Id $savedPid -Force -ErrorAction SilentlyContinue
                $stopped++
            } else {
                Write-Host "  $name: stale PID file (PID=$savedPid)"
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 2

# Segundo barrido por nombre (cubre procesos no rastreados)
foreach ($name in $names) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        Write-Host "  stopping orphan $name (PID=$($p.Id))..."
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        $stopped++
    }
}

# Python services (uvicorn) que no siempre exponen .exe con el nombre del servicio
$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "E:\\TNSVT-V2-Architecture"
}
foreach ($p in $pythonProcs) {
    $cmd = $p.CommandLine
    $match = [regex]::Match($cmd, "apps\\(\w+(-\w+)?)")
    $svcName = if ($match.Success) { $match.Groups[1].Value } else { "python-tnsvt" }
    Write-Host "  stopping python $svcName (PID=$($p.Id))..."
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    $stopped++
}

Start-Sleep -Seconds 2

# NATS opcional (solo si lo lanzamos nosotros)
$natsProcs = Get-Process -Name "nats-server" -ErrorAction SilentlyContinue
if ($natsProcs) {
    $answer = Read-Host "  NATS server esta corriendo. Detenerlo? (s/N)"
    if ($answer -eq "s" -or $answer -eq "S") {
        foreach ($p in $natsProcs) {
            Write-Host "  stopping nats-server (PID=$($p.Id))..."
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $stopped++
        }
    }
}

# Verificar puertos libres
Write-Host ""
Write-Host "Verificando puertos..." -ForegroundColor Cyan
$remaining = @()
foreach ($name in $names) {
    $proc = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  [STILL RUNNING] $name" -ForegroundColor Red
        $remaining += $name
    }
}
if ($remaining.Count -eq 0) {
    Write-Host "  Todos los servicios TNSVT detenidos" -ForegroundColor Green
} else {
    Write-Host "  $($remaining.Count) servicios aun corriendo" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Stop completo: $stopped procesos finalizados" -ForegroundColor Cyan
exit ($remaining.Count -gt 0 ? 1 : 0)
