$dir = "C:\Users\HP 240 inch G9\OneDrive\Desktop\Importante ultimas cosas\Terminal_Financiera_Pro_Completo\Terminal_Financiera_Pro"
Set-Location $dir

Start-Process -FilePath "python.exe" -ArgumentList "-m","signal_copier.main" -WorkingDirectory $dir -WindowStyle Hidden
Start-Sleep -Seconds 3
Start-Process -FilePath "python.exe" -ArgumentList "-m","bot.main" -WorkingDirectory $dir -WindowStyle Hidden
Start-Sleep -Seconds 5

Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object {
    $id = $_.Id
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine
    Write-Host "PID $id : $($cmd.Substring(0, [Math]::Min(70, $cmd.Length)))"
}
