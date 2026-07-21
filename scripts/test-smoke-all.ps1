param([switch]$Quiet)

$pass = 0; $fail = 0; $skip = 0
$results = @()

function Test-Url {
    param($Name, $Url, $ExpectedStatus = 200, $ExpectedText = $null)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        $ok = $r.StatusCode -eq $ExpectedStatus
        if ($ok -and $ExpectedText) { $ok = $r.Content -match $ExpectedText }
        if ($ok) { $script:pass++; $results += [PSCustomObject]@{Name=$Name;Result="✅ PASS";Detail="$($r.StatusCode)"} }
        else { $script:fail++; $results += [PSCustomObject]@{Name=$Name;Result="❌ FAIL";Detail="Esperado $ExpectedStatus, obtuvo $($r.StatusCode)"} }
    } catch {
        $script:fail++; $results += [PSCustomObject]@{Name=$Name;Result="❌ FAIL";Detail="No responde: $_"}
    }
}

function Test-Process {
    param($Name, $ProcessName)
    $p = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if ($p) { $script:pass++; $results += [PSCustomObject]@{Name=$Name;Result="✅ PASS";Detail="PID $($p.Id)"} }
    else { $script:fail++; $results += [PSCustomObject]@{Name=$Name;Result="❌ FAIL";Detail="Proceso '$ProcessName' no encontrado"} }
}

function Test-File {
    param($Name, $Path)
    if (Test-Path $Path) { $script:pass++; $results += [PSCustomObject]@{Name=$Name;Result="✅ PASS";Detail=$Path} }
    else { $script:fail++; $results += [PSCustomObject]@{Name=$Name;Result="❌ FAIL";Detail="No existe: $Path"} }
}

Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  TNSVT V2 — Smoke Test Suite" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Infraestructura ──
Write-Host "── Infraestructura ──" -ForegroundColor Yellow
Test-Url "NATS HTTP monitor" "http://localhost:8222/" 200
Test-Url "PostgreSQL" "http://localhost:15432" 200 $null  # skip if fails

# ── Bridge API ──
Write-Host "`n── Bridge API (:8522) ──" -ForegroundColor Yellow
Test-Url "Health" "http://localhost:8522/health" 200 "ok"
Test-Url "MT5 Accounts" "http://localhost:8522/mt5/accounts" 200
Test-Url "Copier Status" "http://localhost:8522/copier/status" 200
Test-Url "Copier Dashboard" "http://localhost:8522/copier/trades?limit=5" 200

# ── Vite Frontend ──
Write-Host "`n── Frontend (:5180) ──" -ForegroundColor Yellow
Test-Url "Vite app" "http://localhost:5180" 200
Test-Url "Proxy MT5 accounts" "http://localhost:5180/api/v1/mt5/accounts" 200
Test-Url "Proxy Admin" "http://localhost:5180/api/v1/admin/tenants" 200

# ── Go Gateway ──
Write-Host "`n── API Gateway (:8080) ──" -ForegroundColor Yellow
Test-Url "Gateway health" "http://localhost:8080/health" 200

# ── MT5 Snapshots ──
Write-Host "`n── MT5 Snapshots ──" -ForegroundColor Yellow
Test-File "accounts.json" "D:\TradingBotMT5\accounts.json"
Test-File "account_snapshot" "D:\TradingBotMT5\account_snapshot.json"

# ── Procesos ──
Write-Host "`n── Procesos ──" -ForegroundColor Yellow
Test-Process "NATS Server" "nats-server"
Test-Process "Bridge API" "python"
Test-Process "Vite dev" "node"
Test-Process "MT5 Terminal" "terminal64"

# ── Resumen ──
Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  RESULTADOS" -ForegroundColor Cyan
Write-Host "  ✅ Pass: $pass   ❌ Fail: $fail   ⏭️ Skip: $skip" -ForegroundColor $(if ($fail -eq 0) {"Green"} else {"Red"})
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan

if ($fail -gt 0 -and !$Quiet) {
    Write-Host "`n── Detalle de fallos ──" -ForegroundColor Red
    $results | Where-Object { $_.Result -eq "❌ FAIL" } | Format-Table Name, Detail -AutoSize
}
