# TNSVT V2 — start nativo (sin Docker)
# Levanta postgres/redis/nats nativos + 13 servicios TNSVT.
# Reintenta bind si el puerto está ocupado. Propaga env desde .env.

$ErrorActionPreference = 'Continue'

$repo = "E:\TNSVT-V2-Architecture"
$bin = Join-Path $repo "bin"
$logs = Join-Path $repo "logs"
$pidDir = Join-Path $repo "run"

New-Item -ItemType Directory -Force -Path $logs, $pidDir | Out-Null

# ─── Load .env into Process scope ────────────────────────────
Get-Content (Join-Path $repo ".env") | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $idx = $_.IndexOf('=')
    if ($idx -gt 0) {
        $key = $_.Substring(0, $idx).Trim()
        $val = $_.Substring($idx + 1).Trim()
        [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
    }
}

Write-Host "=== TNSVT V2 start nativo ===" -ForegroundColor Cyan
Write-Host "JWT_SECRET length: $(if ($env:JWT_SECRET) { $env:JWT_SECRET.Length } else { 0 })"
Write-Host "NATS host: $env:NATS_HOST port: $env:NATS_PORT" -ForegroundColor Gray
Write-Host ""

# ─── Services in order ────────────────────────────────────────
$services = @(
    @{ name = "account-manager";  exe = "account-manager.exe";  port = 8510; py = $false },
    @{ name = "auth-service";     exe = "auth-service.exe";     port = 8001; py = $false },
    @{ name = "signal-engine";    exe = "signal-engine.exe";    port = 8003; py = $false },
    @{ name = "risk-engine";      exe = "risk-engine.exe";      port = 8006; py = $false },
    @{ name = "audit-engine";     exe = "audit-engine.exe";     port = 8600; py = $false },
    @{ name = "execution-engine"; exe = "execution-engine.exe"; port = 8004; py = $false },
    @{ name = "copy-trading";     exe = "copy-trading.exe";     port = 8005; py = $false },
    @{ name = "orchestrator";     exe = "orchestrator";        port = 8060; py = $true; cwd = "apps/ai/orchestrator" },
    @{ name = "liquidity-engine"; exe = "liquidity-engine";    port = 8050; py = $true; cwd = "apps/ai/liquidity-engine" },
    @{ name = "news-analyzer";    exe = "news-analyzer";       port = 8051; py = $true; cwd = "apps/ai/news-analyzer" },
    @{ name = "macro-fetcher";    exe = "macro-fetcher";       port = 8040; py = $true; cwd = "apps/data/macro-fetcher" },
    @{ name = "news-bridge";      exe = "news-bridge";        port = 0;    py = $true; cwd = "apps/integrations/news-bridge" },
    @{ name = "mt5-connector";    exe = "mt5-connector.exe";   port = 8007; py = $false },
    @{ name = "api-gateway";      exe = "api-gateway.exe";     port = 8000; py = $false }
)

# ─── Stop existing (por PID file y por nombre) ────────────────
foreach ($svc in $services) {
    $pidFile = Join-Path $pidDir "$($svc.name).pid"
    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($oldPid -and ($oldPid -match '^\d+$')) {
            Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}
foreach ($svc in $services) {
    Get-Process -Name $svc.exe -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "E:\\TNSVT-V2-Architecture\\apps"
} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

# ─── NATS server (solo si no esta corriendo) ─────────────────
$natsRunning = Get-Process -Name "nats-server" -ErrorAction SilentlyContinue
if (-not $natsRunning) {
    Write-Host "[NATS] Iniciando NATS JetStream..." -ForegroundColor Yellow
    $natsProc = Start-Process -FilePath (Join-Path $bin "nats-server.exe") `
        -ArgumentList "-c", (Join-Path $repo "config\nats.conf") `
        -RedirectStandardOutput (Join-Path $logs "nats-stdout.log") `
        -RedirectStandardError (Join-Path $logs "nats-stderr.log") `
        -PassThru -WindowStyle Hidden
    Write-Host "  nats-server PID: $($natsProc.Id)"
    Start-Sleep -Seconds 3
    $natsReady = $false
    for ($i = 0; $i -lt 10; $i++) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port 4222 -InformationLevel Quiet) {
            $natsReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if ($natsReady) {
        Write-Host "  NATS listo en 4222" -ForegroundColor Green
    } else {
        Write-Host "  NATS no respondio en 4222" -ForegroundColor Red
    }
}

# ─── Start services con retry ─────────────────────────────────
function Start-TnsvtService {
    param($svc, $attempt = 1)

    $name = $svc.name
    $logFile = Join-Path $logs "$name.log"
    $errFile = Join-Path $logs "$name.log.err"
    $pidFile = Join-Path $pidDir "$name.pid"

    Write-Host "[$attempt] Starting $name..." -NoNewline

    $proc = $null
    try {
        if ($svc.py) {
            $cwd = Join-Path $repo $svc.cwd
            $args = @()
            if ($name -eq "news-bridge") {
                $args = @((Join-Path $repo "apps\integrations\news-bridge\main.py"))
            } else {
                $args = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$($svc.port)")
            }
            $proc = Start-Process -FilePath "python" -ArgumentList $args `
                -WorkingDirectory $cwd `
                -RedirectStandardOutput $logFile -RedirectStandardError $errFile `
                -PassThru -WindowStyle Hidden
        } else {
            $exe = Join-Path $bin $svc.exe
            $proc = Start-Process -FilePath $exe -WorkingDirectory $bin `
                -RedirectStandardOutput $logFile -RedirectStandardError $errFile `
                -PassThru -WindowStyle Hidden
        }
    } catch {
        Write-Host " FAILED ($($_.Exception.Message))"
        return
    }

    if ($proc -and $proc.Id -gt 0) {
        $proc.Id | Out-File -FilePath $pidFile -Encoding ASCII
        Write-Host " PID=$($proc.Id)"
    } else {
        Write-Host " FAILED"
        return
    }

    if ($svc.port -gt 0) {
        $ready = $false
        for ($i = 0; $i -lt 25; $i++) {
            Start-Sleep -Seconds 1
            try {
                $client = New-Object System.Net.Sockets.TcpClient
                $iar = $client.BeginConnect('127.0.0.1', $svc.port, $null, $null)
                $ok = $iar.AsyncWaitHandle.WaitOne(500, $false)
                if ($ok) {
                    $client.EndConnect($iar)
                    $client.Close()
                    $ready = $true
                    break
                }
                $client.Close()
            } catch {}
        }
        if (-not $ready) {
            Write-Host "    $name did not bind port $($svc.port) in 25s" -ForegroundColor Yellow
            Write-Host "    Check: $errFile" -ForegroundColor Gray
        } else {
            Write-Host "    listening on $($svc.port)" -ForegroundColor DarkGray
        }
    }
}

foreach ($svc in $services) {
    Start-TnsvtService -svc $svc -attempt 1
}

Write-Host ""
Write-Host "=== Status ===" -ForegroundColor Cyan
$running = 0
$stale = 0
foreach ($svc in $services) {
    $pidFile = Join-Path $pidDir "$($svc.name).pid"
    if (Test-Path $pidFile) {
        $savedPid = Get-Content $pidFile
        $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
        if ($proc) {
            $portStr = if ($svc.port -gt 0) { $svc.port } else { "(NATS)" }
            Write-Host "  $($svc.name.PadRight(20)) running PID=$savedPid port=$portStr" -ForegroundColor Green
            $running++
        } else {
            Write-Host "  $($svc.name.PadRight(20)) stale PID=$savedPid" -ForegroundColor Yellow
            $stale++
        }
    } else {
        Write-Host "  $($svc.name.PadRight(20)) not started" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Resumen: $running running, $stale stale" -ForegroundColor Cyan
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Yellow
Write-Host "  1. python scripts/register_admin.py   # crea usuario admin"
Write-Host "  2. python scripts/register_lst_account.py  # (opcional, ya auto-registrado)"
Write-Host "  3. Instalar EA MQL5 en terminal MT5 (C:\Program Files\MetaTrader 5\terminal64.exe)"
Write-Host "  4. curl http://localhost:8050/health  # smoke test"
Write-Host "  5. Frontend: cd apps/frontend && npm install && npm run dev"
