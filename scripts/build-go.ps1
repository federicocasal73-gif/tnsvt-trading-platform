$svc_list = @(
    "trading/execution-engine",
    "gateway/api-gateway",
    "platform/account-manager",
    "trading/signal-engine",
    "broker/mt5-connector",
    "risk/risk-engine",
    "trading/copy-trading",
    "platform/auth-service",
    "platform/user-service",
    "audit/audit-engine"
)
$repo = "E:\TNSVT-V2-Architecture"
foreach ($svc in $svc_list) {
    $name = Split-Path $svc -Leaf
    $out = Join-Path $repo "bin\$name.exe"
    Write-Host "Building $name..." -NoNewline
    Push-Location (Join-Path $repo "apps\$svc")
    go build -ldflags="-w -s" -o $out . 2>&1 | Out-Null
    Pop-Location
    if (Test-Path $out) {
        Write-Host " OK ($([math]::Round((Get-Item $out).Length / 1MB, 1)) MB)"
    } else {
        Write-Host " FAILED"
    }
}
