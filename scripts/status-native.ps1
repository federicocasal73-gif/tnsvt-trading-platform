# TNSVT V2 — status nativo
# Muestra PID + puerto + health para cada servicio del stack.

$repo = "E:\TNSVT-V2-Architecture"
$pidDir = Join-Path $repo "run"

$services = @(
    @{ name = "account-manager";  exe = "account-manager.exe";  port = 8510; health = "/health" },
    @{ name = "auth-service";     exe = "auth-service.exe";     port = 8001; health = "/health" },
    @{ name = "signal-engine";    exe = "signal-engine.exe";    port = 8003; health = "/health" },
    @{ name = "execution-engine"; exe = "execution-engine.exe"; port = 8004; health = "/health" },
    @{ name = "risk-engine";      exe = "risk-engine.exe";      port = 8006; health = "/health" },
    @{ name = "mt5-connector";    exe = "mt5-connector.exe";    port = 8007; health = "/health" },
    @{ name = "macro-fetcher";    exe = "macro-fetcher";        port = 8040; health = "/health"; py = $true },
    @{ name = "liquidity-engine"; exe = "liquidity-engine";    port = 8050; health = "/health"; py = $true },
    @{ name = "news-analyzer";    exe = "news-analyzer";       port = 8051; health = "/health"; py = $true },
    @{ name = "orchestrator";     exe = "orchestrator";        port = 8060; health = "/api/v1/orchestrator/health"; py = $true },
    @{ name = "news-bridge";      exe = "news-bridge";         port = 0;    health = ""; py = $true },
    @{ name = "api-gateway";      exe = "api-gateway.exe";     port = 8000; health = "/health" },
    @{ name = "audit-engine";     exe = "audit-engine.exe";    port = 8600; health = "/health" },
    @{ name = "copy-trading";     exe = "copy-trading.exe";    port = 8005; health = "/health" }
)

function Get-Health($port, $healthPath = "/health") {
    if ($port -le 0) { return $null }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port$healthPath" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $r.StatusCode
    } catch { return $null }
}

function Get-PidByName($name) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) { return ($procs | Select-Object -First 1).Id }
    return $null
}

function Get-PidFromFile($name) {
    $pidFile = Join-Path $pidDir "$name.pid"
    if (Test-Path $pidFile) {
        $content = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($content -and ($content -match '^\d+$')) { return [int]$content }
    }
    return $null
}

Write-Host "=== TNSVT V2 status ===" -ForegroundColor Cyan
Write-Host ""
Write-Host ("  {0,-18} {1,-8} {2,-8} {3,-12}" -f "Service", "PID", "Port", "Health")
Write-Host ("  {0,-18} {1,-8} {2,-8} {3,-12}" -f ("-" * 18), ("-" * 8), ("-" * 8), ("-" * 12))

foreach ($svc in $services) {
    $svcPid = Get-PidFromFile $svc.name
    if (-not $svcPid) { $svcPid = Get-PidByName $svc.exe }
    $portStr = if ($svc.port -gt 0) { $svc.port } else { "(NATS)" }
    $healthCode = Get-Health $svc.port $svc.health
    $healthStr = if ($healthCode -eq $null) { "-" } elseif ($healthCode -eq 200) { "OK 200" } else { "HTTP $healthCode" }

    $pidStr = if ($svcPid) { "$svcPid" } else { "-" }
    $rowColor = if (-not $svcPid) { "Yellow" } elseif ($healthCode -ne 200) { "Yellow" } else { "Green" }

    Write-Host ("  {0,-18} {1,-8} {2,-8} {3,-12}" -f $svc.name, $pidStr, $portStr, $healthStr) -ForegroundColor $rowColor
}

Write-Host ""
Write-Host "Infraestructura:" -ForegroundColor Cyan
$pgSvc = Get-Service -Name postgresql-x64-16 -ErrorAction SilentlyContinue
$rdSvc = Get-Service -Name Redis -ErrorAction SilentlyContinue
$natsProc = Get-Process -Name "nats-server" -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("  PostgreSQL:    {0}" -f $(if ($pgSvc.Status -eq "Running") { "OK $($pgSvc.Name)" } else { "STOPPED" }))
Write-Host ("  Redis:          {0}" -f $(if ($rdSvc.Status -eq "Running") { "OK $($rdSvc.Name)" } else { "STOPPED" }))
Write-Host ("  NATS JetStream: {0}" -f $(if ($natsProc) { "OK PID=$($natsProc.Id)" } else { "STOPPED" }))

Write-Host ""
Write-Host "LST Account:" -ForegroundColor Cyan
$lstId = $env:LST_ACCOUNT_ID
if (-not $lstId) {
    $envFile = Join-Path $repo ".env"
    if (Test-Path $envFile) {
        $m = Select-String -Path $envFile -Pattern "^LST_ACCOUNT_ID=(.+)$"
        if ($m) { $lstId = $m.Matches.Groups[1].Value }
    }
}
if ($lstId) {
    Write-Host "  account_id: $lstId" -ForegroundColor Green
} else {
    Write-Host "  account_id: NO REGISTRADA -- ejecuta scripts/run-lst-bootstrap.ps1" -ForegroundColor Red
}
