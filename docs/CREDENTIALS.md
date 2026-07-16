# TNSVT V2 — Demo Credentials

> **⚠️  These credentials are for local development and demos ONLY. Do NOT use
> them in production. Production must use strong, unique passwords, hashed
> with bcrypt (cost ≥ 12), and JWTs must use a strong secret from a secret
> manager.**

This document lists every default credential, token, and demo
identity baked into TNSVT V2 for local development.

---

## 1. Frontend demo user (Vite/React)

When you run the frontend in demo mode without the full auth-service
backend, the frontend decodes the JWT from `localStorage` to extract the
user's identity. The placeholder JWT used by the Playwright e2e suite
and the screenshot scripts has these claims:

| Field        | Value                                        |
|--------------|----------------------------------------------|
| `sub` / `user_id` | `00000000-0000-0000-0000-000000000001`    |
| `tenant_id`  | `00000000-0000-0000-0000-000000000001`        |
| `email`      | `demo@tnsvt.com`                             |
| `username`   | `demo`                                       |
| `role`       | `admin`                                      |
| `exp`        | far future (effectively non-expiring)        |

The token is unsigned (`alg: "none"`) — **never** ship a real auth
backend that accepts these.

### Login bypass (manual)

To skip the login page in dev:

1. Open the frontend at `http://localhost:5180`
2. In the browser DevTools console:
   ```js
   localStorage.setItem('tnsvt_token', '<paste unsigned JWT>');
   location.reload();
   ```

You can mint an unsigned JWT at <https://jwt.io> with `alg: "none"` and
the claims above. The frontend will accept any well-formed JWT (three
base64url-encoded segments separated by dots).

---

## 2. auth-service default user (when seeded via `scripts/seed.sh`)

After running `make seed` (or `bash scripts/seed.sh`), the
`platform.users` table contains:

| Field           | Value                  |
|-----------------|------------------------|
| `id`            | `00000000-0000-0000-0000-000000000002` |
| `tenant_id`     | `00000000-0000-0000-0000-000000000001` |
| `email`         | `admin@tnsvt.local`     |
| `username`      | `admin`                 |
| `password_hash` | bcrypt cost-10 (see seed.sh) |
| `role`          | `admin`                 |

The seeded password is `Admin123!Demo` (see `scripts/seed.sh`).

> The bcrypt hash in `scripts/seed.sh` is a pre-computed value for
> `Admin123!Demo`. If you change the password in the seed, regenerate
> the hash with `htpasswd -bnBC 10 "" your_password` (truncate the
> ":" prefix).

---

## 3. PostgreSQL (database)

Configured in `infrastructure/postgres/init.sql` and `.env.example`.

| Field    | Default      |
|----------|--------------|
| Host     | `postgres`   |
| Port     | `5432`       |
| Database | `tnsvt`      |
| User     | `tnsvt`      |
| Password | `tnsvt`      |

Connection string (in-network):
`postgresql://tnsvt:tnsvt@postgres:5432/tnsvt`

Direct psql access from the host:
```
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U tnsvt -d tnsvt
```

---

## 4. NATS (messaging)

| Field      | Default          |
|------------|------------------|
| URL        | `nats://nats:4222` |
| Monitoring | `http://localhost:8222` |
| Stream     | `MARKETDATA` (subjects `marketdata.>`), `TRADING_SIGNALS` (`trading.signal.>`) |

No credentials in dev (NATS is unauthenticated). Production should
enable token-based auth.

---

## 5. Redis (cache + session store)

| Field    | Default       |
|----------|---------------|
| Host     | `redis`        |
| Port     | `6379`         |
| DBs      | 0 (shared), 3 (ai-core), 4 (regime-detector) |
| Password | *(empty in dev)* |

---

## 6. Ollama (LLM)

| Field    | Default           |
|----------|-------------------|
| URL      | `http://ollama:11434` |
| Models   | `llama3.2:3b` (default), `llama3:8b`, `mixtral:8x7b`, `phi-3:3.8b` |

After the first run, pull the default model:
```
docker compose -f docker-compose.dev.yml exec ollama ollama pull llama3.2:3b
```

---

## 7. Monitoring endpoints

| Service        | URL                          | Credentials          |
|----------------|------------------------------|----------------------|
| Prometheus     | `http://localhost:9090`      | (none)               |
| Grafana        | `http://localhost:3001`      | `admin` / `admin`    |
| Traefik dash   | `http://localhost:8080`      | (none)               |
| NATS monitor   | `http://localhost:8222`      | (none)               |
| Node Exporter  | `http://localhost:9100`      | (none)               |
| pg Exporter    | `http://localhost:9187`      | (none)               |
| Redis Exporter | `http://localhost:9121`      | (none)               |

---

## 8. Default service ports (dev)

| Service             | Port  |
|---------------------|-------|
| api-gateway         | 8000  |
| auth-service        | 8001  |
| signal-engine       | 8003  |
| execution-engine    | 8004  |
| copy-trading        | 8005  |
| risk-engine         | 8006  |
| mt5-connector       | 8007  |
| ai-core             | 8200  |
| regime-detector     | 8201  |
| price-feed          | 8300  |
| user-service        | 8401  |
| telegram-bot-service| 8503  |
| audit-engine        | 8600  |
| frontend (vite)     | 5180  |

Frontend proxies `/api` → `localhost:8000` (api-gateway) by default.
Override with `VITE_API_TARGET=http://localhost:8300 npm run dev` to
proxy directly to the price-feed (useful for the e2e demo without
spinning up the gateway).

---

## 9. JWT secret (auth-service)

In `infrastructure/postgres/init.sql` and `.env.example`:
```
JWT_SECRET=change-me-in-production-this-is-32-chars-min
```

For dev, any 32+ char string works. For production, generate with:
```
openssl rand -base64 48
```

---

## 10. Reset everything

```bash
# Stop all containers
bash scripts/stop.sh

# Wipe all data
bash scripts/stop.sh --volumes

# Restart from scratch with seed data
bash scripts/start.sh --seed
```

This recreates all Postgres schemas, drops Redis state, and re-seeds the
default tenant + admin user.