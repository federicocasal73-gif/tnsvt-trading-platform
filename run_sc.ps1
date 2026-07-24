Set-Location "E:\TNSVT-V2-Architecture\apps\integrations\tnsvt-bot"
python signal_copier/main.py *>&1 | Out-File -FilePath "E:\TNSVT-V2-Architecture\sc_live.log" -Append
