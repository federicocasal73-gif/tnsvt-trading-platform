$env:PYTHONPATH = "E:\TNSVT-V2-Architecture\apps\data\macro-fetcher"
$proc = Start-Process python -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8040" -WorkingDirectory "E:\TNSVT-V2-Architecture\apps\data\macro-fetcher" -RedirectStandardOutput "E:\TNSVT-V2-Architecture\logs\macro-fetcher.log" -RedirectStandardError "E:\TNSVT-V2-Architecture\logs\macro-fetcher.log.err" -PassThru -WindowStyle Hidden
Write-Host "macro-fetcher PID: $($proc.Id)"
Start-Sleep -Seconds 3
Test-NetConnection -ComputerName 127.0.0.1 -Port 8040 -InformationLevel Quiet
