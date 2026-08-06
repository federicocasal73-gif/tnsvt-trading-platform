$bin = 'E:\TNSVT-V2-Architecture\bin'
$exe = Join-Path $bin 'api-gateway.exe'
$logFile = 'E:\TNSVT-V2-Architecture\logs\gateway.log'
$errFile = 'E:\TNSVT-V2-Architecture\logs\gateway.log.err'
$repo = 'E:\TNSVT-V2-Architecture'

# Load .env
$envVars = @{}
Get-Content (Join-Path $repo '.env') | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $idx = $_.IndexOf('=')
    if ($idx -gt 0) {
        $key = $_.Substring(0, $idx).Trim()
        $val = $_.Substring($idx + 1).Trim()
        $envVars[$key] = $val
    }
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.WorkingDirectory = $bin
$psi.RedirectStandardOutput = $logFile
$psi.RedirectStandardError = $errFile
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
foreach ($kv in $envVars.GetEnumerator()) {
    $psi.EnvironmentVariables[$kv.Key] = $kv.Value
}

$proc = [System.Diagnostics.Process]::Start($psi)
Write-Host "Gateway PID: $($proc.Id)"
Start-Sleep 3

# Check if port 8000 is listening
$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $iar = $tcp.BeginConnect('127.0.0.1', 8000, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(3000, $false)
    if ($ok) {
        $tcp.EndConnect($iar)
        Write-Host "Gateway listening on port 8000"
    } else {
        Write-Host "Gateway did not bind to port 8000 in 3s - check logs"
        Get-Content $errFile -Tail 10 -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "Gateway connection failed: $($_.Exception.Message)"
} finally {
    $tcp.Close()
}
