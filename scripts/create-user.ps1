#!/usr/bin/env pwsh
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Crear usuario demo via API
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

$API_URL = "http://localhost:8001/api/v1/auth"
$GATEWAY_URL = "http://localhost:8000/api/v1/auth"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host "  TNSVT V2 - Crear usuario demo"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$email = "admin@tnsvt.local"
$password = "Admin123!Demo"
$tenantName = "TNSVT Demo"
$username = "admin"

$body = @{
    tenant_name = $tenantName
    email       = $email
    username    = $username
    password    = $password
} | ConvertTo-Json

Write-Host "Probando endpoint directo auth-service: $API_URL"
try {
    $response = Invoke-RestMethod -Uri "$API_URL/register" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "OK: Usuario creado via auth-service" -ForegroundColor Green
    Write-Host ""
    Write-Host "Credenciales demo:" -ForegroundColor Cyan
    Write-Host "  Email:    $email"
    Write-Host "  Password: $password"
    Write-Host ""
    exit 0
} catch {
    Write-Host "  auth-service: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "Probando via api-gateway: $GATEWAY_URL"
try {
    $response = Invoke-RestMethod -Uri "$GATEWAY_URL/register" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "OK: Usuario creado via api-gateway" -ForegroundColor Green
    Write-Host ""
    Write-Host "Credenciales demo:" -ForegroundColor Cyan
    Write-Host "  Email:    $email"
    Write-Host "  Password: $password"
    Write-Host ""
    exit 0
} catch {
    Write-Host "  api-gateway: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "ERROR: No se pudo conectar a ningun endpoint." -ForegroundColor Red
Write-Host "Verifica que docker compose este corriendo: docker compose -f docker-compose.dev.yml up -d" -ForegroundColor Red
Write-Host ""
exit 1
