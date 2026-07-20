$dir = "C:\Users\HP 240 inch G9\OneDrive\Desktop\Importante ultimas cosas\Terminal_Financiera_Pro_Completo\Terminal_Financiera_Pro"
Set-Location $dir

# Kill any existing python processes (except our shell)
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start Signal Copier
Start-Process -FilePath "python.exe" -ArgumentList "-m","signal_copier.main" -WorkingDirectory $dir -WindowStyle Hidden
Write-Host "Signal Copier started"
Start-Sleep -Seconds 3

# Start Bridge API (FastAPI)
Start-Process -FilePath "python.exe" -ArgumentList "api_server.py" -WorkingDirectory $dir -WindowStyle Hidden
Write-Host "Bridge API started"
Start-Sleep -Seconds 2

# Start Bot
Start-Process -FilePath "python.exe" -ArgumentList "-m","bot.main" -WorkingDirectory $dir -WindowStyle Hidden
Write-Host "Bot started"
Start-Sleep -Seconds 3

# Start Dashboard (Streamlit)
Start-Process -FilePath "streamlit" -ArgumentList "run","dashboard/app.py","--server.port","8501","--server.headless","true" -WorkingDirectory $dir -WindowStyle Hidden
Write-Host "Dashboard started"

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "=== Procesos Activos ==="
Get-Process -Name "python", "streamlit" -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, @{N="StartTime";E={$_.StartTime.ToString("HH:mm:ss")}} | Format-Table -AutoSize
