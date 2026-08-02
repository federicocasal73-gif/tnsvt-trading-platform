$env:BRIDGE_API_PORT = "8522"
$env:DEFAULT_TENANT_ID = "d028c9ec-6257-4d38-8a55-7ba6dd4f2b9b"

Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "bridge-api"
} | Stop-Process -Force
Start-Sleep -Seconds 2

Set-Location "E:\TNSVT-V2-Architecture\apps\bridge\bridge-api"
$proc = Start-Process -FilePath "python" -ArgumentList "main.py" `
    -WorkingDirectory "E:\TNSVT-V2-Architecture\apps\bridge\bridge-api" `
    -RedirectStandardOutput "E:\TNSVT-V2-Architecture\logs\bridge-api.log" `
    -RedirectStandardError "E:\TNSVT-V2-Architecture\logs\bridge-api.log.err" `
    -PassThru -WindowStyle Hidden
Write-Host "bridge-api PID: $($proc.Id)"
Start-Sleep -Seconds 4
$ready = Test-NetConnection -ComputerName 127.0.0.1 -Port 8522 -InformationLevel Quiet
Write-Host "8522 listening: $ready"
