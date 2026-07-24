# install_autostart.ps1 — Instala auto-arranque TNSVT V2 en Windows
$err= $ErrorActionPreference; $ErrorActionPreference= 'Stop'
$ROOT = 'E:\TNSVT-V2-Architecture'
$SCRIPT = "$ROOT\start_all.ps1"
$LOGD = "$ROOT\logs"
$BAT = "$ROOT\start_all_autostart.bat"

if (!(Test-Path $LOGD)) { mkdir $LOGD -Force | Out-Null }

if (!(Test-Path $SCRIPT)) {
    Write-Host "ERROR: no se encuentra $SCRIPT" -ForegroundColor Red; exit 1
}

$bt = '@echo off', "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$SCRIPT`" >> `"$LOGD\autostart.log`" 2>&1"
$bt -join "`r`n" | Set-Content $BAT -Encoding ASCII

Write-Host '======================================' -ForegroundColor Cyan
Write-Host '  Auto-Arranque TNSVT V2' -ForegroundColor Yellow
Write-Host '======================================' -ForegroundColor Cyan
Write-Host ''

$adminOk = $false
try {
    $p = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if ($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Modo ADMIN: registrando Task Scheduler...' -ForegroundColor Green
        $tn = 'TNSVT-StartAll'
        $ex = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
        if ($ex) { Unregister-ScheduledTask -TaskName $tn -Confirm:$false; Start-Sleep 1 }
        $a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$BAT`"" -WorkingDirectory $ROOT
        $tr = New-ScheduledTaskTrigger -AtLogOn
        $st = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0 -Priority 7
        Register-ScheduledTask -TaskName $tn -Action $a -Trigger $tr -Settings $st -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited -Force | Out-Null
        Write-Host "Task Scheduler '$tn' OK" -ForegroundColor Green
        $adminOk = $true
    }
} catch { Write-Host 'Task Scheduler: requiere admin' -ForegroundColor Yellow }

# Startup shortcut
$sd = [Environment]::GetFolderPath('Startup')
$lnk = Join-Path $sd 'TNSVT-StartAll.lnk'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = 'cmd.exe'
$sc.Arguments = "/c start /B `"$BAT`""
$sc.WorkingDirectory = $ROOT
$sc.Description = 'TNSVT V2'
$sc.WindowStyle = 7
$sc.Save()
Write-Host "Startup shortcut: $lnk" -ForegroundColor Green
Write-Host ''
Write-Host 'COMPLETADO' -ForegroundColor Green
Write-Host ''
if ($adminOk) { Write-Host '  Task Scheduler: TNSVT-StartAll (al iniciar sesion)' }
else { Write-Host '  Task Scheduler: NO (ejecuta como Admin si queres)' }
Write-Host '  Startup folder: siempre activo'
Write-Host ''
Write-Host 'Probar ahora:' -ForegroundColor Cyan
Write-Host "  $BAT"
Write-Host ''
Write-Host 'Desinstalar:' -ForegroundColor Cyan
Write-Host "  Remove-Item '$lnk' -Force; Remove-Item '$BAT' -Force"

$ErrorActionPreference = $err
