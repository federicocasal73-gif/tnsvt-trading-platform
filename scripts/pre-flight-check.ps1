#requires -Version 5.1
<#
TNSVT V2 — pre-flight check unificado
Detecta automaticamente modo Docker vs nativo y valida prerrequisitos.
#>

$script:Pass = 0
$script:Fail = 0

function Test-Item {
    param([bool]$Ok, [string]$Name, [string]$Hint = "")
    if ($Ok) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:Pass++
    } else {
        Write-Host "  [FAIL] $Name $Hint" -ForegroundColor Red
        $script:Fail++
    }
}

Write-Host "== TNSVT V2 pre-flight check ==" -ForegroundColor Cyan
Write-Host ""

# Detectar modo
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
$mode = "native"
if ($dockerCmd) {
    try {
        $null = docker info 2>&1
        if ($LASTEXITCODE -eq 0) { $mode = "docker" }
    } catch {}
}
Write-Host "Modo detectado: $mode" -ForegroundColor $(if ($mode -eq "docker") { "Cyan" } else { "Yellow" })
Write-Host ""

# ─── [1/6] .env file ──────────────────────────────────────
Write-Host "[1/6] .env file" -ForegroundColor Cyan
$envPath = Join-Path $PSScriptRoot "..\.env"
$envExamplePath = Join-Path $PSScriptRoot "..\.env.example"
$hasEnv = Test-Path $envPath
Test-Item $hasEnv ".env existe en repo root" "(copy .env.example .env)"

if ($hasEnv) {
    $envContent = Get-Content $envPath -Raw
    Test-Item ($envContent -match "LST_LOGIN=12345678") "LST_LOGIN=12345678"
    Test-Item ($envContent -match "LST_SERVER=YourBroker-MT5") "LST_SERVER=YourBroker-MT5"
    $pwdEmpty = $envContent -match "LST_PASSWORD=$"
    Test-Item (-not $pwdEmpty) "LST_PASSWORD no vacio"
    Test-Item ($envContent -match "DEFAULT_TENANT_ID=[0-9a-f-]{36}") "DEFAULT_TENANT_ID es UUID valido"
    Test-Item ($envContent -match "JWT_SECRET=.+") "JWT_SECRET set"
    Test-Item ($envContent -match "MT5_PATH=.*terminal64\.exe") "MT5_PATH apunta a terminal64.exe"
}

# ─── [2/6] MT5 terminal (NO TOCAR) ─────────────────────────
Write-Host ""
Write-Host "[2/6] MT5 terminal" -ForegroundColor Cyan
$mt5Paths = @(
    "C:\Program Files\MetaTrader 5\terminal64.exe",
    "C:\Program Files\FTMO MetaTrader 5\terminal64.exe"
)
$mt5Found = $false
foreach ($p in $mt5Paths) {
    if (Test-Path $p) {
        Write-Host "  [OK] $p" -ForegroundColor Green
        $mt5Found = $true
    }
}
if (-not $mt5Found) {
    Write-Host "  [FAIL] no MT5 terminal en paths esperados" -ForegroundColor Red
    $script:Fail++
}

# ─── [3/6] Binarios ────────────────────────────────────────
Write-Host ""
Write-Host "[3/6] Binarios compilados" -ForegroundColor Cyan
$binDir = Join-Path $PSScriptRoot "..\bin"
Test-Item (Test-Path (Join-Path $binDir "nats-server.exe")) "bin/nats-server.exe"
$goBins = @("account-manager.exe","auth-service.exe","signal-engine.exe","execution-engine.exe",
            "risk-engine.exe","mt5-connector.exe","api-gateway.exe","audit-engine.exe","copy-trading.exe")
foreach ($b in $goBins) {
    Test-Item (Test-Path (Join-Path $binDir $b)) "bin/$b"
}

# ─── [4/6] Modo nativo: infraestructura ──────────────────
if ($mode -eq "native") {
    Write-Host ""
    Write-Host "[4/6] Infraestructura nativa" -ForegroundColor Cyan
    $pgSvc = Get-Service -Name postgresql-x64-16 -ErrorAction SilentlyContinue
    Test-Item ($pgSvc -and $pgSvc.Status -eq "Running") "PostgreSQL 16 corriendo"
    if ($pgSvc) {
        $envContent = Get-Content $envPath -Raw
        $pgPass = ($envContent -match "POSTGRES_PASSWORD=(\S+)")
        if ($pgPass) {
            try {
                $env:PGPASSWORD = $Matches[1]
                $test = & psql -U tnsvt -h localhost -c "SELECT 1" 2>&1
                Test-Item ($LASTEXITCODE -eq 0) "PostgreSQL user=tnsvt/db=tnsvt conecta"
            } catch {
                Test-Item $false "PostgreSQL conecta" "(verificar credenciales)"
            } finally {
                Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
            }
        }
    }
    $rdSvc = Get-Service -Name Redis -ErrorAction SilentlyContinue
    Test-Item ($rdSvc -and $rdSvc.Status -eq "Running") "Redis corriendo"
    $natsProc = Get-Process -Name "nats-server" -ErrorAction SilentlyContinue | Select-Object -First 1
    Test-Item ($natsProc -ne $null) "NATS server corriendo (PID=$($natsProc.Id))"
} else {
    Write-Host ""
    Write-Host "[4/6] Docker daemon" -ForegroundColor Cyan
    try { $null = docker info 2>&1; Test-Item ($LASTEXITCODE -eq 0) "Docker daemon responde" } catch { Test-Item $false "Docker daemon" }
}

# ─── [5/6] Puertos ────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Puertos criticos" -ForegroundColor Cyan
$ports = @(8000,8001,8003,8004,8005,8006,8007,8040,8050,8051,8060,8200,8300,8510,8522,8600)
foreach ($p in $ports) {
    $inUse = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    $occupied = $null -ne $inUse
    if ($occupied) {
        Write-Host "  [INFO] puerto $p ya en uso (servicio nativo?)" -ForegroundColor DarkGray
    } else {
        Write-Host "  [OK]   puerto $p libre" -ForegroundColor Green
        $script:Pass++
    }
}

# ─── [6/6] Servicios construidos ──────────────────────────
Write-Host ""
Write-Host "[6/6] Servicios Python" -ForegroundColor Cyan
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\integrations\news-bridge\main.py")) "news-bridge/main.py"
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\integrations\lst-account-bootstrap\main.py")) "lst-account-bootstrap/main.py"
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\ai\liquidity-engine\app\main.py")) "liquidity-engine/app/main.py"
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\ai\orchestrator\app\main.py")) "orchestrator/app/main.py"
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\ai\news-analyzer\app\main.py")) "news-analyzer/app/main.py"
Test-Item (Test-Path (Join-Path $PSScriptRoot "..\apps\data\macro-fetcher\app\main.py")) "macro-fetcher/app/main.py"

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "PASS: $script:Pass  FAIL: $script:Fail" -ForegroundColor $(if ($script:Fail -eq 0) { "Green" } else { "Red" })
Write-Host "================================" -ForegroundColor Cyan

if ($script:Fail -gt 0) {
    Write-Host ""
    Write-Host "Acciones sugeridas:" -ForegroundColor Yellow
    if (-not $hasEnv) {
        Write-Host "  - Copiar .env.example a .env y completar credenciales"
    }
    if (-not $mt5Found) {
        Write-Host "  - Verificar que el terminal MT5 este instalado (NO reiniciar)"
    }
    $missingBins = $goBins | Where-Object { -not (Test-Path (Join-Path $binDir $_)) }
    if ($missingBins) {
        Write-Host "  - Compilar binarios: powershell -File scripts/build-go.ps1"
    }
    if ($mode -eq "native") {
        if (-not (Get-Service -Name postgresql-x64-16 -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" })) {
            Write-Host "  - Iniciar PostgreSQL: Start-Service postgresql-x64-16"
        }
        if (-not (Get-Service -Name Redis -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" })) {
            Write-Host "  - Iniciar Redis: Start-Service Redis"
        }
        if (-not (Get-Process -Name nats-server -ErrorAction SilentlyContinue)) {
            Write-Host "  - NATS no esta corriendo; scripts/start-native.ps1 lo arranca"
        }
    }
    exit 1
}

Write-Host ""
Write-Host "Todo listo para arrancar:" -ForegroundColor Green
if ($mode -eq "docker") {
    Write-Host "  .\scripts\go-live-lst.ps1"
} else {
    Write-Host "  .\scripts\start-native.ps1"
    Write-Host "  python scripts/register_admin.py"
    Write-Host "  python scripts/register_lst_account.py  # o via docker"
}
exit 0
