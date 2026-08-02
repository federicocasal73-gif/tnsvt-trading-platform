$ErrorActionPreference = 'Stop'

$repo = "E:\TNSVT-V2-Architecture"
$logOut = Join-Path $repo "logs\news-bridge.log"
$logErr = Join-Path $repo "logs\news-bridge.log.err"
$pidFile = Join-Path $repo "run\news-bridge.pid"

# Stop existing
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "news-bridge\\main\.py"
} | Stop-Process -Force
Get-Content $pidFile -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\d+$' } | ForEach-Object {
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Cargar .env y construir hashtable
$envMap = @{}
Get-Content (Join-Path $repo ".env") | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $idx = $_.IndexOf('=')
    if ($idx -gt 0) {
        $key = $_.Substring(0, $idx).Trim()
        $val = $_.Substring($idx + 1).Trim()
        $envMap[$key] = $val
    }
}

# Defaults especificos para news-bridge
if (-not $envMap.ContainsKey("NATS_URL") -or -not $envMap["NATS_URL"]) { $envMap["NATS_URL"] = "nats://localhost:4222" }
if (-not $envMap.ContainsKey("NEWS_SUBJECT") -or -not $envMap["NEWS_SUBJECT"]) { $envMap["NEWS_SUBJECT"] = "trading.signal.news_based" }
if (-not $envMap.ContainsKey("NATS_STREAM") -or -not $envMap["NATS_STREAM"]) { $envMap["NATS_STREAM"] = "tnsvt" }
if (-not $envMap.ContainsKey("NEWS_BRIDGE_DURABLE") -or -not $envMap["NEWS_BRIDGE_DURABLE"]) { $envMap["NEWS_BRIDGE_DURABLE"] = "news-bridge" }
if (-not $envMap.ContainsKey("SIGNAL_ENGINE_URL") -or -not $envMap["SIGNAL_ENGINE_URL"]) { $envMap["SIGNAL_ENGINE_URL"] = "http://localhost:8003" }
if (-not $envMap.ContainsKey("SIGNAL_INGEST_API_KEY") -or -not $envMap["SIGNAL_INGEST_API_KEY"]) { $envMap["SIGNAL_INGEST_API_KEY"] = "dev-ingest-key" }

Write-Host "Starting news-bridge con env propagado..."

# Set env vars en el shell actual (Start-Process hereda de parent)
foreach ($k in $envMap.Keys) {
    [System.Environment]::SetEnvironmentVariable($k, $envMap[$k], 'Process')
}

$proc = Start-Process -FilePath "python" `
    -ArgumentList "E:\TNSVT-V2-Architecture\apps\integrations\news-bridge\main.py" `
    -WorkingDirectory "E:\TNSVT-V2-Architecture\apps\integrations\news-bridge" `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr `
    -PassThru -WindowStyle Hidden

$proc.Id | Out-File -FilePath $pidFile -Encoding ASCII
Write-Host "PID: $($proc.Id)"
Start-Sleep -Seconds 3

# Verificar que arranco correctamente
$log = Get-Content $logOut -Tail 5 -ErrorAction SilentlyContinue
if ($log -match "NATS connected") {
    Write-Host "news-bridge OK" -ForegroundColor Green
} else {
    Write-Host "news-bridge no arranco correctamente" -ForegroundColor Red
    Write-Host $log
}
