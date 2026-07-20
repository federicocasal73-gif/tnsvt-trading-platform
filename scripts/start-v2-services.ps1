$base = "E:\TNSVT-V2-Architecture"
$logDir = "$base\services_logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$services = @(
    @{Name="api-gateway";    Dir="$base\apps\gateway\api-gateway";                  Port=8000; Env=$null},
    @{Name="risk-engine";    Dir="$base\apps\risk\risk-engine";                  Port=8006; Env=$null},
    @{Name="price-feed";     Dir="$base\apps\market-data\price-feed";            Port=8300; Env=$null},
    @{Name="auth-service";   Dir="$base\apps\platform\auth-service";             Port=8001; Env=$null},
    @{Name="user-service";   Dir="$base\apps\platform\user-service";             Port=8401; Env=$null},
    @{Name="signal-engine";  Dir="$base\apps\trading\signal-engine";             Port=8003; Env=$null},
    @{Name="copy-trading";   Dir="$base\apps\trading\copy-trading";              Port=8005; Env=$null},
    @{Name="telegram-bot-service"; Dir="$base\apps\notification\telegram-bot-service"; Port=8503; Env=$null}
)

foreach ($svc in $services) {
    $portFree = (Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0
    if (-not $portFree) {
        Write-Host "$($svc.Name) port $($svc.Port) IN USE - skip"
        continue
    }
    $exe = Join-Path $svc.Dir "$($svc.Name).exe"
    if (-not (Test-Path $exe)) {
        Write-Host "$($svc.Name) executable NOT FOUND at $exe - skip"
        continue
    }
    $logFile = "$logDir\$($svc.Name).log"
    $errFile = "$logDir\$($svc.Name).err"
    Start-Process -FilePath $exe -WorkingDirectory $svc.Dir -WindowStyle Hidden -RedirectStandardOutput $logFile -RedirectStandardError $errFile
    Write-Host "Started $($svc.Name) (port $($svc.Port))"
}

Start-Sleep -Seconds 5
Write-Host ""
Write-Host "=== Estado final de puertos V2 ==="
$ports = 8000,8001,8003,8004,8005,8006,8401,8503,8300,8600
foreach ($p in $ports) {
    $proc = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc) {
        $pname = (Get-Process -Id $proc.OwningProcess).ProcessName
        Write-Host "  $p $pname (PID $($proc.OwningProcess))"
    } else {
        Write-Host "  $p OFF"
    }
}
