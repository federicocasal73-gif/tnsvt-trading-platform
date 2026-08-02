$ErrorActionPreference = 'Stop'

$repo = "E:\TNSVT-V2-Architecture"
$bin = Join-Path $repo "bin"
$logOut = Join-Path $repo "logs\copy-trading.log"
$logErr = Join-Path $repo "logs\copy-trading.log.err"
$pidFile = Join-Path $repo "run\copy-trading.pid"

# Stop existing
Get-Process -Name "copy-trading" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Content $pidFile -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\d+$' } | ForEach-Object {
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Load .env into Process scope
Get-Content (Join-Path $repo ".env") | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $idx = $_.IndexOf('=')
    if ($idx -gt 0) {
        $key = $_.Substring(0, $idx).Trim()
        $val = $_.Substring($idx + 1).Trim()
        [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
    }
}

# copy-trading defaults
if (-not $env:COPY_TRADING_PORT) { $env:COPY_TRADING_PORT = "8005" }
if (-not $env:EXECUTION_ENGINE_URL) { $env:EXECUTION_ENGINE_URL = "http://localhost:8004" }
if (-not $env:COPY_TRADING_MAX_ACCOUNTS) { $env:COPY_TRADING_MAX_ACCOUNTS = "20" }
if (-not $env:COPY_TRADING_TIMEOUT_SECONDS) { $env:COPY_TRADING_TIMEOUT_SECONDS = "60" }

Write-Host "Starting copy-trading..."
$proc = Start-Process -FilePath (Join-Path $bin "copy-trading.exe") -WorkingDirectory $bin `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr `
    -PassThru -WindowStyle Hidden

$proc.Id | Out-File -FilePath $pidFile -Encoding ASCII
Write-Host "PID: $($proc.Id)"

$ready = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', 8005, $null, $null)
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
if ($ready) {
    Write-Host "  copy-trading listening on 8005" -ForegroundColor Green
} else {
    Write-Host "  copy-trading did not bind port 8005" -ForegroundColor Red
    Get-Content $logErr -Tail 20
    exit 1
}
