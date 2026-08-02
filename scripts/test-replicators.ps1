$body = '{"email":"admin@tnsvt.io","password":"Admin123!Pass"}'
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5
$token = ($r.Content | ConvertFrom-Json).access_token
$h = @{ Authorization = "Bearer $token" }
$tid = "d028c9ec-6257-4d38-8a55-7ba6dd4f2b9b"
$h["X-Tenant-ID"] = $tid

Write-Host "[1] GET /api/v1/accounts (todas)"
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/accounts" -Headers $h -UseBasicParsing -TimeoutSec 5
$accounts = ($r.Content | ConvertFrom-Json).accounts
Write-Host "  total: $($accounts.Count)"
foreach ($a in $accounts) {
    Write-Host "  - $($a.alias) login=$($a.login) copy_enabled=$($a.copy_enabled)"
}

Write-Host ""
Write-Host "[2] GET /api/v1/accounts/replicators"
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/accounts/replicators" -Headers $h -UseBasicParsing -TimeoutSec 5
    Write-Host "  HTTP $($r.StatusCode)"
    $replicators = ($r.Content | ConvertFrom-Json).accounts
    Write-Host "  replicators: $($replicators.Count)"
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "[3] PATCH copy_enabled=true en demo_main"
$demo = $accounts | Where-Object { $_.alias -like "*demo*" } | Select-Object -First 1
if ($demo) {
    Write-Host "  target: $($demo.alias) (id=$($demo.id))"
    $patchBody = '{"copy_enabled": true}'
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/accounts/$($demo.id)" -Method PUT -Headers $h -ContentType "application/json" -Body $patchBody -UseBasicParsing -TimeoutSec 5
        Write-Host "  HTTP $($r.StatusCode)"
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "[4] GET /api/v1/accounts/replicators (despues de toggle)"
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/accounts/replicators" -Headers $h -UseBasicParsing -TimeoutSec 5
$replicators = ($r.Content | ConvertFrom-Json).accounts
Write-Host "  replicators: $($replicators.Count)"
foreach ($a in $replicators) {
    Write-Host "  - $($a.alias) login=$($a.login) copy_enabled=$($a.copy_enabled)"
}

Write-Host ""
Write-Host "[5] PATCH copy_enabled=false (rollback)"
if ($demo) {
    $patchBody = '{"copy_enabled": false}'
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/accounts/$($demo.id)" -Method PUT -Headers $h -ContentType "application/json" -Body $patchBody -UseBasicParsing -TimeoutSec 5
        Write-Host "  HTTP $($r.StatusCode)"
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)"
    }
}
