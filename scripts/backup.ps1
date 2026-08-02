$ErrorActionPreference = "Stop"
$BackupDir = "E:\TNSVT-Backup\$(Get-Date -Format 'yyyy-MM-dd_HH-mm')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

function backup-file($src, $dst) {
    if (Test-Path $src) {
        $dir = Split-Path $dst
        if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "[OK] $src"
    } else {
        Write-Host "[SKIP] $src (not found)"
    }
}

Write-Host "=== TNSVT Backup ==="
Write-Host "Dest: $BackupDir`n"

Write-Host "[1/6] .env files..."
backup-file ".env" "$BackupDir/root.env"
backup-file "apps/bridge/bridge-api/.env" "$BackupDir/bridge-api.env"
backup-file "apps/integrations/tnsvt-bot/.env" "$BackupDir/tnsvt-bot.env"
backup-file "apps/auth-service/.env" "$BackupDir/auth-service.env"

Write-Host "`n[2/6] Bridge DBs..."
backup-file "apps/bridge/bridge-api/bridge_outbox.db" "$BackupDir/bridge_outbox.db"
backup-file "apps/bridge/bridge-api/admin_db.sqlite" "$BackupDir/admin_db.sqlite"

Write-Host "`n[3/6] pg_dump tnsvt..."
$pgDump = "$BackupDir\tnsvt_dump.sql"
try {
    & pg_dump -U postgres -d tnsvt --no-owner --no-acl > $pgDump 2>$null
    if ((Test-Path $pgDump) -and (Get-Item $pgDump).Length -gt 0) {
        Write-Host "[OK] tnsvt dump written"
    } else {
        Write-Host "[WARN] pg_dump produced empty file"
    }
} catch {
    Write-Host "[WARN] pg_dump not available"
}

Write-Host "`n[4/6] Telegram session..."
foreach ($name in @("tnsvt-bot", "tnsvt-bot2", "signal_copier\session")) {
    foreach ($ext in @("session", "session-journal")) {
        $src = "apps/integrations/tnsvt-bot/bot/$name.$ext"
        if (!(Test-Path $src)) { $src = "apps/integrations/tnsvt-bot/$name.$ext" }
        backup-file $src "$BackupDir/$name.$ext"
    }
}

Write-Host "`n[5/6] NATS JetStream data..."
if (Test-Path "data/nats/jetstream") {
    $dstDir = "$BackupDir/nats-jetstream"
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    Copy-Item -Path "data/nats/jetstream" -Destination $dstDir -Recurse -Force
    Write-Host "[OK] data/nats/jetstream"
} else {
    Write-Host "[SKIP] data/nats/jetstream (not found)"
}

Write-Host "`n[6/6] Logs..."
foreach ($log in @("logs\bridge-api.log","logs\bot.log","logs\auth-service.log")) {
    backup-file $log "$BackupDir\logs\$(Split-Path $log -Leaf)"
}

Write-Host "`n=== Done ==="
Write-Host "Backup: $BackupDir"
$size = (Get-ChildItem $BackupDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "Size: $([math]::Round($size/1MB, 1)) MB"
