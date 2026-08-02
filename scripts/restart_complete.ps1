param([switch]$NoWait)

$ROOT = "E:\TNSVT-V2-Architecture"
$LOG = "$ROOT\_logs"
New-Item -ItemType Directory -Path $LOG -Force | Out-Null

function Start-Svc($Name, $Dir, $Cmd, $Port) {
    $logFile = "$LOG\$Name.log"
    $errFile = "$LOG\$Name.err.log"
    Remove-Item $logFile -Force -ErrorAction SilentlyContinue
    Remove-Item $errFile -Force -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath "cmd" -ArgumentList "/c cd /d `"$Dir`" && $Cmd > `"$logFile`" 2> `"$errFile`"" -WindowStyle Hidden -PassThru
    Write-Host "  $Name (:${Port}) lanzado (PID $($proc.Id))" -ForegroundColor Yellow
    return $proc
}

function Check-Port($Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return ($c -ne $null)
}

# ── Matar previos ──
Write-Host "=== Matando procesos previos ===" -ForegroundColor Cyan
foreach ($p in @(8000,8001,8003,8004,8005,8006,8007,8050,8060,8100,8200,8201,8300,8401,8503,8522,8600,5180)) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($c) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 3
Write-Host "  Procesos anteriores eliminados" -ForegroundColor Green

# ── Infra ──
Write-Host "`n=== Infraestructura ===" -ForegroundColor Cyan
foreach ($svc in @(@{Port=5432;Name="PostgreSQL"},@{Port=6379;Name="Redis"},@{Port=4222;Name="NATS"},@{Port=3001;Name="Grafana"})) {
    if (Check-Port $svc.Port) { Write-Host "  ✓ $($svc.Name) (:$( $svc.Port ))" -ForegroundColor Green }
    else { Write-Host "  ✗ $($svc.Name) (:$( $svc.Port )) DOWN" -ForegroundColor Red }
}

# ── Go Services ──
Write-Host "`n=== Servicios Go ===" -ForegroundColor Cyan
$goSvcs = @(
    @{Name="api-gateway";        Dir="$ROOT\apps\gateway\api-gateway";        Cmd="go run main.go";               Port=8000},
    @{Name="signal-engine";      Dir="$ROOT\apps\trading\signal-engine";      Cmd="go run main.go";               Port=8003},
    @{Name="execution-engine";   Dir="$ROOT\apps\trading\execution-engine";   Cmd="go run main.go";               Port=8004},
    @{Name="copy-trading";       Dir="$ROOT\apps\trading\copy-trading";       Cmd="go run main.go";               Port=8005},
    @{Name="risk-engine";        Dir="$ROOT\apps\risk\risk-engine";           Cmd="go run main.go";               Port=8006},
    @{Name="mt5-connector";      Dir="$ROOT\apps\broker\mt5-connector";      Cmd="go run main.go";               Port=8007},
    @{Name="price-feed";         Dir="$ROOT\apps\market-data\price-feed";     Cmd="go run main.go";               Port=8300},
    @{Name="user-service";       Dir="$ROOT\apps\platform\user-service";      Cmd="go run main.go";               Port=8401},
    @{Name="telegram-bot-svc";   Dir="$ROOT\apps\notification\telegram-bot-service"; Cmd="go run main.go";      Port=8503},
    @{Name="audit-engine";       Dir="$ROOT\apps\audit\audit-engine";         Cmd="go run main.go";               Port=8600}
)

foreach ($svc in $goSvcs) {
    Start-Svc $svc.Name $svc.Dir $svc.Cmd $svc.Port
    Start-Sleep -Milliseconds 500
}

Write-Host "  Esperando 15s para que los Go servicios levanten..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

foreach ($svc in $goSvcs) {
    if (Check-Port $svc.Port) { Write-Host "  ✓ $($svc.Name) (:$( $svc.Port ))" -ForegroundColor Green }
    else { Write-Host "  ✗ $($svc.Name) (:$( $svc.Port )) DOWN" -ForegroundColor Red }
}

# ── Python Services ──
Write-Host "`n=== Servicios Python ===" -ForegroundColor Cyan
$pySvcs = @(
    @{Name="orchestrator";   Dir="$ROOT\apps\ai\orchestrator";       Cmd="uvicorn app.main:app --host 0.0.0.0 --port 8060";           Port=8060},
    @{Name="bridge-api";     Dir="$ROOT\apps\bridge\bridge-api";     Cmd="uvicorn main:app --host 0.0.0.0 --port 8522";               Port=8522},
    @{Name="mcp-trading";    Dir="$ROOT\apps\integrations\mcp-trading-server"; Cmd="python server.py";                              Port=8100},
    @{Name="liquidity-engine"; Dir="$ROOT\apps\ai\liquidity-engine"; Cmd="uvicorn app.main:app --host 0.0.0.0 --port 8050";          Port=8050}
)

foreach ($svc in $pySvcs) {
    Start-Svc $svc.Name $svc.Dir $svc.Cmd $svc.Port
    Start-Sleep -Milliseconds 500
}

Write-Host "  Esperando 15s para que los Python servicios levanten..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

foreach ($svc in $pySvcs) {
    if (Check-Port $svc.Port) { Write-Host "  ✓ $($svc.Name) (:$( $svc.Port ))" -ForegroundColor Green }
    else { Write-Host "  ✗ $($svc.Name) (:$( $svc.Port )) - revisar $LOG\$($svc.Name).log" -ForegroundColor Red }
}

# ── Frontend ──
Write-Host "`n=== Frontend Vite ===" -ForegroundColor Cyan
Start-Svc "frontend" "$ROOT\apps\frontend" "npm run dev" 5180
Start-Sleep -Seconds 8
if (Check-Port 5180) { Write-Host "  ✓ Frontend (:5180)" -ForegroundColor Green } else { Write-Host "  ✗ Frontend (:5180) DOWN" -ForegroundColor Red }

# ── Final ──
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ESTADO FINAL" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
$allPorts = @(8000,8001,8003,8004,8005,8006,8007,8050,8060,8100,8200,8201,8300,8401,8503,8522,8600,5180)
$ok = 0; $fail = 0
$portNames = @{8000="api-gateway";8001="auth-service";8003="signal-engine";8004="execution-engine";8005="copy-trading";8006="risk-engine";8007="mt5-connector";8050="liquidity-engine";8060="orchestrator";8100="mcp-trading";8200="ai-core";8201="regime-detector";8300="price-feed";8401="user-service";8503="telegram-bot";8522="bridge-api";8600="audit-engine";5180="frontend"}
foreach ($p in $allPorts) {
    $name = if ($portNames.ContainsKey($p)) { $portNames[$p] } else { "svc-$p" }
    if (Check-Port $p) { Write-Host "  ✓ $name (:${p})" -ForegroundColor Green; $ok++ }
    else { Write-Host "  ✗ $name (:${p})" -ForegroundColor Red; $fail++ }
}
Write-Host "`n  $ok OK, $fail FAIL" -ForegroundColor Cyan
Write-Host "`nLogs: $LOG" -ForegroundColor Cyan
Write-Host "URLs:  Frontend http://localhost:5180 | Gateway http://localhost:8000 | Orchestrator http://localhost:8060" -ForegroundColor Cyan
