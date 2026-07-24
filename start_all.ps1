# start_all.ps1 — Arranca todo el stack TNSVT V2 en un solo comando
#
# Servicios:
#   1. Bridge API   :8522
#   2. Bot Telegram (python-telegram-bot)
#   3. Vite Frontend :5180
#   4. Signal Copier (Telethon + MT5)
#
# Uso:  powershell -ExecutionPolicy Bypass -File .\start_all.ps1

param(
    [switch]$NoKill = $false,
    [int]$WaitSec = 12
)

$ErrorActionPreference = "Continue"
$ROOT = "E:\TNSVT-V2-Architecture"
$LOG_DIR = "$ROOT\logs"
New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null

function Write-Section {
    param([string]$Title)
    $bar = "=" * 60
    Write-Host ""
    Write-Host $bar -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Yellow
    Write-Host $bar -ForegroundColor Cyan
}

function Stop-IfRunning {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pid = $conn.OwningProcess
        Write-Host "  Puerto $Port ocupado por PID $pid - matando..." -ForegroundColor Red
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 400
        } catch {}
    }
}

function Get-PidByPort {
    param([int]$Port)
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return $c.OwningProcess | Select-Object -First 1 }
    return $null
}

# --- Paso 1: limpiar procesos previos ---
if (-not $NoKill) {
    Write-Section "Paso 1: Limpiando procesos previos"

    Get-Process -Name python, node, npm -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.ProcessName
        $id = $_.Id
        try {
            Write-Host "  Matando $name (PID $id)" -ForegroundColor Red
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Start-Sleep -Seconds 2

    Stop-IfRunning 8522
    Stop-IfRunning 5180
    Start-Sleep -Seconds 1
}

# --- Paso 2: Bridge API ---
Write-Section "Paso 2: Arrancando Bridge API (:8522)"

$bridgeDir = Join-Path $ROOT "apps\bridge\bridge-api"
$bridgeLog = Join-Path $ROOT "bridge.log"
$bridgeErrLog = Join-Path $ROOT "bridge.log.err"

if (Test-Path $bridgeDir) {
    $bridgeProc = Start-Process -FilePath "python" `
        -ArgumentList "main.py" `
        -WorkingDirectory $bridgeDir `
        -RedirectStandardOutput $bridgeLog `
        -RedirectStandardError $bridgeErrLog `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "  PID $($bridgeProc.Id) - log: $bridgeLog"
} else {
    Write-Host "  [WARN] $bridgeDir no existe" -ForegroundColor Red
}

# --- Paso 3: Vite Frontend ---
Write-Section "Paso 3: Arrancando Vite Frontend (:5180)"

$frontendDir = Join-Path $ROOT "apps\frontend"
$viteLog = Join-Path $ROOT "vite_live.log"

if (Test-Path (Join-Path $frontendDir "package.json")) {
    $viteCmd = "cd /d `"$frontendDir`" && npm run dev > `"$viteLog`" 2>&1"
    $viteProc = Start-Process -FilePath "cmd" `
        -ArgumentList "/c $viteCmd" `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "  PID $($viteProc.Id) - log: $viteLog"
} else {
    Write-Host "  [WARN] $frontendDir no existe" -ForegroundColor Red
}

# --- Paso 4: Bot Telegram ---
Write-Section "Paso 4: Arrancando Bot Telegram"

$botDir = Join-Path $ROOT "apps\integrations\tnsvt-bot"
$botLog = Join-Path $botDir "bot.log"
$botErrLog = Join-Path $botDir "bot.log.err"

if (Test-Path (Join-Path $botDir "bot\main.py")) {
    $botProc = Start-Process -FilePath "python" `
        -ArgumentList "bot\main.py" `
        -WorkingDirectory $botDir `
        -RedirectStandardOutput $botLog `
        -RedirectStandardError $botErrLog `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "  PID $($botProc.Id) - log: $botLog"
} else {
    Write-Host "  [WARN] $botDir no existe" -ForegroundColor Red
}

# --- Paso 5: Signal Copier ---
Write-Section "Paso 5: Arrancando Signal Copier (Telethon + MT5)"

$scScript = Join-Path $ROOT "run_sc.ps1"
$scLog = Join-Path $ROOT "sc_live.log"

if (Test-Path $scScript) {
    $scProc = Start-Process -FilePath "pwsh" `
        -ArgumentList "-ExecutionPolicy Bypass -File `"$scScript`"" `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "  PID $($scProc.Id) - log: $scLog"
} else {
    Write-Host "  [WARN] $scScript no existe" -ForegroundColor Red
}

# --- Paso 6: Esperar y reportar ---
Write-Section "Paso 6: Esperando arranque ($WaitSec s)..."
Start-Sleep -Seconds $WaitSec

Write-Section "Status Final"

$bridgePid = Get-PidByPort 8522
$vitePid = Get-PidByPort 5180
$botPid = if ($botProc) { $botProc.Id } else { $null }
$scPid = if ($scProc) { $scProc.Id } else { $null }

function Status-Line([string]$Name, $Pid, $Cmd) {
    if ($null -ne $Pid -and (Get-Process -Id $Pid -ErrorAction SilentlyContinue)) {
        Write-Host ("  {0,-15} {1,-8} [OK]" -f $Name, $Pid) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-15} {1,-8} [DOWN]" -f $Name, "-") -ForegroundColor Red
    }
}

Write-Host ""
Write-Host ("  {0,-15} {1,-8} {2,-10}" -f "Servicio", "PID", "Status")
Write-Host ("  {0,-15} {1,-8} {2,-10}" -f "-------", "---", "------")

Status-Line "Bridge API" $bridgePid
Status-Line "Bot" $botPid
Status-Line "Vite" $vitePid
Status-Line "Signal Copier" $scPid

Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
if ($bridgePid) { Write-Host "  Bridge API:    http://localhost:8522/docs" }
if ($vitePid) { Write-Host "  Frontend Vite: http://localhost:5180" }
Write-Host "  Bot (Telegram): @terminalfinancieraproTNSVT_bot"
Write-Host ""
Write-Host "Logs:" -ForegroundColor Cyan
Write-Host "  Bridge:    $bridgeLog"
Write-Host "  Vite:      $viteLog"
Write-Host "  Bot:       $botLog"
Write-Host "  Copier:    $scLog"
Write-Host ""
