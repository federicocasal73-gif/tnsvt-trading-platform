Set-Location "E:\TNSVT-V2-Architecture\apps\integrations\tnsvt-bot"
# Cargar .env del bot (no pisa variables de entorno del sistema)
$envFile = Join-Path $PWD ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if (-not [System.Environment]::GetEnvironmentVariable($key, 'Process')) {
                [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
            }
        }
    }
}
# UTF-8 for stdout (evita UnicodeEncodeError con emojis/flchas en logs)
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
python signal_copier/main.py *>&1 | Out-File -FilePath "E:\TNSVT-V2-Architecture\sc_live.log" -Append -Encoding utf8
