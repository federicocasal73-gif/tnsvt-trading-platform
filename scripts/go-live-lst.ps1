# TNSVT V2 — go-live LST (YourBroker)
# Levanta docker-compose, espera health, verifica rutas del gateway.

$ErrorActionPreference = 'Stop'

Write-Host "== TNSVT V2 go-live LST ==" -ForegroundColor Cyan

Write-Host ""
Write-Host "[0/5] Pre-flight check..." -ForegroundColor Cyan
& "$PSScriptRoot\pre-flight-check.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pre-flight check fallo. Corrige los problemas y vuelve a intentar." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path .env)) {
    Write-Host "No existe .env; copiando .env.example" -ForegroundColor Yellow
    Copy-Item .env.example .env
}

Write-Host "[1/4] Levantando docker compose..." -ForegroundColor Cyan
docker compose -f docker-compose.dev.yml up -d

Write-Host "[2/4] Esperando health checks..." -ForegroundColor Cyan
$services = @(
    @{ Name = "postgres";      Url = "http://localhost:5432" },
    @{ Name = "redis";         Url = "http://localhost:6379" },
    @{ Name = "nats";          Url = "http://localhost:8222/healthz" },
    @{ Name = "account-manager"; Url = "http://localhost:8510/health" },
    @{ Name = "mt5-connector"; Url = "http://localhost:8007/health" },
    @{ Name = "liquidity-engine"; Url = "http://localhost:8050/health" },
    @{ Name = "orchestrator";  Url = "http://localhost:8060/api/v1/orchestrator/health" },
    @{ Name = "news-analyzer"; Url = "http://localhost:8051/health" },
    @{ Name = "macro-fetcher"; Url = "http://localhost:8040/health" }
)

foreach ($svc in $services) {
    $ok = $false
    for ($i = 1; $i -le 30; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $svc.Url -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                Write-Host "  $($svc.Name): OK" -ForegroundColor Green
                $ok = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ok) {
        Write-Host "  $($svc.Name): TIMEOUT" -ForegroundColor Red
    }
}

Write-Host "[3/4] Esperando lst-account-bootstrap (registra cuenta LST)..." -ForegroundColor Cyan
$lstId = $null
for ($i = 1; $i -le 60; $i++) {
    $status = docker inspect tnsvt-lst-account-bootstrap --format='{{.State.Status}}' 2>$null
    $exitCode = docker inspect tnsvt-lst-account-bootstrap --format='{{.State.ExitCode}}' 2>$null
    if ($status -eq "exited" -and $exitCode -eq 0) {
        Write-Host "  lst-account-bootstrap: OK (exit 0)" -ForegroundColor Green
        $lstId = docker inspect tnsvt-lst-account-bootstrap --format='{{range .Args}}{{println .}}{{end}}' 2>$null
        break
    }
    if ($status -eq "exited" -and $exitCode -ne 0) {
        Write-Host "  lst-account-bootstrap: FAILED (exit $exitCode)" -ForegroundColor Red
        docker logs tnsvt-lst-account-bootstrap --tail 50
        exit 1
    }
    Start-Sleep -Seconds 2
}

if (-not $lstId) {
    Write-Host "  lst-account-bootstrap no terminó; el UUID se obtendrá vía logs" -ForegroundColor Yellow
    docker logs tnsvt-lst-account-bootstrap --tail 5
}

$uuidFile = "/var/run/tnsvt/secrets/lst_account_id"
if (Test-Path $uuidFile) {
    $lstId = Get-Content $uuidFile -Raw
    $lstId = $lstId.Trim()
    Write-Host "  LST account id: $lstId" -ForegroundColor Cyan
}

Write-Host "[4/4] Smoke tests del gateway..." -ForegroundColor Cyan
$gatewayTests = @(
    @{ Name = "news latest";      Url = "http://localhost:8000/api/v1/news/latest?limit=5" },
    @{ Name = "macro indicators"; Url = "http://localhost:8000/api/v1/macro/indicators" },
    @{ Name = "lst zones latest"; Url = "http://localhost:8000/api/v1/lst/zones/latest?symbol=XAUUSD&timeframe=H1" },
    @{ Name = "orchestrator health"; Url = "http://localhost:8000/api/v1/orchestrator/health" },
    @{ Name = "lst health";        Url = "http://localhost:8000/api/v1/lst/health" }
)

foreach ($t in $gatewayTests) {
    try {
        $r = Invoke-WebRequest -Uri $t.Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host "  $($t.Name): HTTP $($r.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "  $($t.Name): FAIL ($($_.Exception.Message))" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "== go-live completo ==" -ForegroundColor Cyan
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Yellow
Write-Host "  1. Compilar EA MQL5: copia apps/broker/mt5-liquidity/MQL5/* a tu terminal"
Write-Host "  2. Tools > Options > Expert Advisors > Allow WebRequest: http://localhost:8050"
Write-Host "  3. Arrastrar EA LiquidityZones al chart XAUUSD H1"
Write-Host "  4. Verificar logs MT5: 'Published N zones to localhost:8050/zones (status=200)'"
Write-Host "  5. Frontend: http://localhost:5180 > Dashboard / News / Macro / Signals"
