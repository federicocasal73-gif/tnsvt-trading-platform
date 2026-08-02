# lst-account-bootstrap

Init container one-shot que registra la cuenta LST en account-manager.

## Que hace

- Espera a que `account-manager` responda `/health` (hasta 60s).
- `GET /api/v1/accounts` y busca una cuenta con el mismo `(login, server)` bajo el tenant.
- Si existe: recupera el UUID y lo escribe.
- Si no existe: `POST /api/v1/accounts` con las credenciales y escribe el UUID devuelto.
- Escribe el UUID en `$LST_ACCOUNT_ID_FILE` (default `/var/run/tnsvt/secrets/lst_account_id`).
- Idempotente: no falla si la cuenta ya existe.

## Variables de entorno

| Variable | Default | Descripcion |
|---|---|---|
| `ACCOUNT_MANAGER_URL` | `http://localhost:8510` | URL del account-manager |
| `LST_TENANT_ID` | `00000000-0000-0000-0000-000000000001` | UUID del tenant |
| `LST_LOGIN` | (requerido) | Numero de login MT5 |
| `LST_PASSWORD` | (requerido) | Password de la cuenta |
| `LST_SERVER` | (requerido) | Nombre del server MT5 |
| `LST_BROKER` | `mt5` | Broker identifier |
| `LST_ALIAS` | `LST-Trading` | Alias visible |
| `LST_ACCOUNT_ID_FILE` | `/var/run/tnsvt/secrets/lst_account_id` | Archivo destino del UUID |

## Contrato con execution-engine

`execution-engine` monta el mismo volumen `tnsvt-secrets` y lee el UUID de `$LST_ACCOUNT_ID_FILE`. Si esta vacio, usa `$LST_ACCOUNT_ID` env var como fallback.

## Tests

```bash
python -m pytest tests/
```

17 tests cubren: HTTP helpers, retry/timeout de account-manager, busqueda idempotente, creacion nueva, manejo de errores, escritura de archivo.

## Flow completo

```
docker compose up
  -> postgres, redis, nats, account-manager arrancan
  -> lst-account-bootstrap arranca, espera account-manager health
  -> POST /api/v1/accounts con TopOneTrader
  -> escribe UUID en volumen compartido tnsvt-secrets
  -> exit 0 (one-shot)
  -> execution-engine arranca, lee UUID del archivo
  -> OK: ruteo por source activo
```
