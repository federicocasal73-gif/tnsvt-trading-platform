# watchdog.ps1 - Continuous monitor for TNSVT V2 services
# Installed as Task Scheduler "TNSVT-Watchdog" (AtLogOn, delay 30s)
# Runs as a continuous loop checking services every 60s
#
# Install (admin):   schtasks /Create /SC ONLOGON /DELAY 0000:30 /TN "TNSVT-Watchdog" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File E:\TNSVT-V2-Architecture\watchdog.ps1" /RL LIMITED /F
# Uninstall (admin): schtasks /Delete /TN "TNSVT-Watchdog" /F

param(
    [string]$RootDir = "E:\TNSVT-V2-Architecture",
    [string]$LogFile = "E:\TNSVT-V2-Architecture\logs\watchdog.log",
    [int]$IntervalSec = 60
)

$ErrorActionPreference = "Continue"

$logDir = Split-Path -Parent $LogFile
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts | $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Test-PortOpen {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn.OwningProcess
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            return $procId
        }
    }
    return $null
}

function Find-PythonByScript {
    param([string]$ScriptSubstr)
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "python.exe" }
    $found = @()
    foreach ($proc in $procs) {
        if ($proc.CommandLine -and ($proc.CommandLine -like "*$ScriptSubstr*")) {
            $found += $proc.ProcessId
        }
    }
    return $found
}

# Track last restart time per service to avoid duplicate starts (cooldown 90s)
$lastRestart = @{}

function Ensure-Service {
    param(
        [string]$Name,
        [int]$Port,
        [string]$ScriptMatch,
        [string]$StartCmd,
        [string]$StartArgs,
        [string]$StartWorkDir
    )

    # Step 1: Check if alive
    $alive = $false
    if ($Port -gt 0) {
        $procId = Test-PortOpen -Port $Port
        if ($procId) { $alive = $true }
    } elseif ($ScriptMatch -ne "") {
        $pids = Find-PythonByScript -ScriptSubstr $ScriptMatch
        if ($pids.Count -gt 0) { $alive = $true }
    }

    if ($alive) {
        return
    }

    # Step 2: Cooldown - skip if recently restarted
    $now = Get-Date
    if ($lastRestart.ContainsKey($Name)) {
        $elapsed = ($now - $lastRestart[$Name]).TotalSeconds
        if ($elapsed -lt 90) {
            return
        }
    }

    # Step 3: Restart
    Write-Log "[$Name] DOWN - restarting..."
    $lastRestart[$Name] = $now
    try {
        Start-Process -FilePath $StartCmd -ArgumentList $StartArgs -WorkingDirectory $StartWorkDir -WindowStyle Hidden
        Start-Sleep -Seconds 8
        # Verify
        $check = $false
        if ($Port -gt 0) {
            $procId = Test-PortOpen -Port $Port
            if ($procId) { $check = $true }
        } elseif ($ScriptMatch -ne "") {
            $pids = Find-PythonByScript -ScriptSubstr $ScriptMatch
            if ($pids.Count -gt 0) { $check = $true }
        }
        if ($check) {
            Write-Log "[$Name] OK - restarted"
        } else {
            Write-Log "[$Name] WARN - start command issued but verification failed"
        }
    } catch {
        Write-Log "[$Name] ERROR - $_"
    }
}

Write-Log "WATCHDOG started (interval=${IntervalSec}s)"

# Wait 30s on startup so start_all.ps1 finishes first
Start-Sleep -Seconds 30

while ($true) {
    try {
        Ensure-Service -Name "bridge-api" -Port 8522 -ScriptMatch "" `
            -StartCmd "python" -StartArgs "main.py" `
            -StartWorkDir "$RootDir\apps\bridge\bridge-api"

        $viteDir = "$RootDir\apps\frontend"
        $viteLog = "$RootDir\vite_live.log"
        Ensure-Service -Name "vite" -Port 5180 -ScriptMatch "" `
            -StartCmd "cmd.exe" -StartArgs "/c cd /d `"$viteDir`" && npm run dev > `"$viteLog`" 2>&1" `
            -StartWorkDir $viteDir

        $botDir = "$RootDir\apps\integrations\tnsvt-bot"
        Ensure-Service -Name "bot" -Port 0 -ScriptMatch "bot\main.py" `
            -StartCmd "python" -StartArgs "bot\main.py" `
            -StartWorkDir $botDir

        $scScript = "$RootDir\run_sc.ps1"
        Ensure-Service -Name "signal_copier" -Port 0 -ScriptMatch "signal_copier\main.py" `
            -StartCmd "pwsh" -StartArgs "-ExecutionPolicy Bypass -File `"$scScript`"" `
            -StartWorkDir $RootDir
    } catch {
        Write-Log "WATCHDOG loop error: $_"
    }

    Start-Sleep -Seconds $IntervalSec
}
