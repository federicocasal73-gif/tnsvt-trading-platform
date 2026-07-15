# DOCUMENT 06: SEGURIDAD

## Plataforma de Trading TNSVT V2 — Arquitectura de Seguridad

**Versión:** 2.0.0  
**Fecha:** 2026-07-14  
**Estado:** Producción  
**Autor:** Equipo de Arquitectura TNSVT V2

---

## Tabla de Contenidos

1. [Visión General: Zero Trust](#1-visión-general-zero-trust)
2. [Autenticación OAuth2](#2-autenticación-oauth2)
3. [Estructura JWT](#3-estructura-jwt)
4. [RBAC: Matriz de Roles y Permisos](#4-rbac-matriz-de-roles-y-permisos)
5. [WAF y Rate Limiting](#5-waf-y-rate-limiting)
6. [Cifrado](#6-cifrado)
7. [Gestión de Secretos](#7-gestión-de-secretos)
8. [Rotación de Claves](#8-rotación-de-claves)
9. [Audit Logs Inmutables](#9-audit-logs-inmutables)
10. [Protección Anti-Replay y Anti-Fraude](#10-protección-anti-replay-y-anti-fraude)
11. [2FA (TOTP)](#11-2fa-totp)
12. [Políticas CORS y CSP](#12-políticas-cors-y-csp)

---

## 1. Visión General: Zero Trust

TNSVT V2 implementa un modelo **Zero Trust** donde ningún servicio, usuario o
dispositivo es confiable por defecto. Cada petición debe ser autenticada,
autorizada y validada.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     ARQUITECTURA ZERO TRUST TNSVT V2                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  User   │───►│ Traefik  │───►│   WAF    │───►│   Auth Service   │   │
│  │ Browser │    │ Gateway  │    │ Middleware│    │ (OAuth2 + JWT)   │   │
│  └─────────┘    └──────────┘    └──────────┘    └────────┬─────────┘   │
│                                                          │             │
│                                        ┌─────────────────┴──────────┐  │
│                                        ▼                            �  │
│                              ┌──────────────────┐    ┌──────────────┐│  │
│                              │   RBAC Engine    │───►│ mTLS Service ││  │
│                              │  (12 roles)      │    │   Mesh       ││  │
│                              └────────┬─────────┘    └──────┬───────┘│  │
│                                       │                      │        │
│                  ┌────────────────────┼──────────────────────┤        │
│                  ▼                    ▼                      ▼        │
│         ┌──────────────┐    ┌──────────────┐      ┌──────────────┐   │
│         │ Trading Core │    │  AI Engine   │      │ Audit Store  │   │
│         │ (Go mTLS)    │    │ (Python mTLS)│      │ (append-only)│   │
│         └──────────────┘    └──────────────┘      └──────────────┘   │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Capa Transversal: Vault, WIF, mTLS, Audit Logs, Rate Limit   │   │
│  └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Principios Zero Trust Implementados

| Principio                          | Implementación                                    |
|------------------------------------|----------------------------------------------------|
| Nunca confiar, siempre verificar   | mTLS + JWT en cada llamada inter-servicio         |
| Menor privilegio                   | RBAC con 12 roles y permisos granulares           |
| Microsegmentación                  | Network policies en K8s, aislamiento por namespace|
| Suponer brecha                     | Audit logs inmutables, detección de anomalías    |
| Verificar explícitamente           | Validación de JWT en cada gateway, no solo al login|
| Datos en tránsito cifrados         | TLS 1.3 obligatorio en todos los endpoints       |

---

## 2. Autenticación OAuth2

### 2.1 Authorization Code + PKCE (Usuarios Web/App)

Utilizado para usuarios autenticándose desde el navegador o la app de escritorio.

```
┌──────────┐                ┌──────────┐                ┌──────────┐
│  Client  │   1. code_     │  Auth    │                │ Resource │
│ (Next.js │   challenge    │  Server  │                │  Server  │
│  /Tauri) │───────────────►│          │                │          │
│          │                │          │                │          │
│          │   2. Redirect  │          │                │          │
│          │◄───────────────│          │                │          │
│          │                │          │                │          │
│          │   3. code +    │          │                │          │
│          │   code_verifier│          │                │          │
│          │───────────────►│          │                │          │
│          │                │  4. Verify                │          │
│          │                │  code_verifier            │          │
│          │                │  against code_challenge   │          │
│          │   5. Tokens    │          │                │          │
│          │◄───────────────│          │                │          │
│          │                │          │                │          │
│          │   6. API call  │          │                │          │
│          │   (access_token)           │                │          │
│          │────────────────────────────────────────────►│          │
│          │                │          │                │  7. Verify│
│          │                │          │                │  JWT      │
│          │   8. Response  │          │                │          │
│          │◄────────────────────────────────────────────│          │
└──────────┘                └──────────┘                └──────────┘
```

**Parámetros PKCE:**

| Parámetro         | Valor                                       |
|-------------------|---------------------------------------------|
| `code_challenge`  | SHA256(code_verifier), Base64URL encoded    |
| `code_challenge_method` | `S256`                               |
| `code_verifier`   | 43-128 chars, charset: [A-Za-z0-9-._~]     |
| `response_type`   | `code`                                      |
| `scope`           | `openid profile email trading:read trading:write` |
| `state`           | CSRF token, 32 bytes random                 |

### 2.2 Client Credentials (Servicio a Servicio)

Utilizado para comunicación entre microservicios internos.

```
┌──────────┐    1. client_id +     ┌──────────┐
│ Service  │    client_secret      │  Auth    │
│ (Go/Py)  │──────────────────────►│  Server  │
│          │                       │          │
│          │    2. access_token    │          │
│          │◄──────────────────────│          │
│          │                       └──────────┘
│          │
│          │    3. API call con Bearer token
│          │──────────────────────────────────► Service B
│          │
└──────────┘
```

**Configuración de Client Credentials:**

| Servicio             | Client ID                | Scopes                                     |
|----------------------|--------------------------|--------------------------------------------|
| Trading Engine       | `svc-trading-engine`     | `risk:read broker:write audit:write`       |
| Risk Engine          | `svc-risk-engine`        | `trading:read risk:write notification:write`|
| AI Engine            | `svc-ai-engine`          | `trading:read ai:write`                    |
| Broker Gateway       | `svc-broker-gateway`     | `trading:read broker:write market:read`    |
| Notification Service | `svc-notification`       | `notification:write`                       |
| Copy Trading         | `svc-copy-trading`       | `trading:read trading:write risk:read`     |
| Platform API         | `svc-platform-api`       | `platform:read platform:write`             |
| Audit Service        | `svc-audit`              | `audit:write audit:read`                   |

---

## 3. Estructura JWT

### 3.1 Access Token (15 minutos)

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-2026-07-14-001"
  },
  "payload": {
    "iss": "https://auth.tnsvt.com",
    "sub": "user_xyz789",
    "aud": ["api.tnsvt.com", "trading.tnsvt.com"],
    "exp": 1752504600,
    "iat": 1752503700,
    "nbf": 1752503700,
    "jti": "jti_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "scope": "openid profile trading:read trading:write",
    "roles": ["tenant_trader"],
    "tenant_id": "tenant_abc123",
    "org_id": "org_def456",
    "mfa_verified": true,
    "device_id": "device_001"
  }
}
```

### 3.2 Refresh Token (7 días)

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-2026-07-14-001"
  },
  "payload": {
    "iss": "https://auth.tnsvt.com",
    "sub": "user_xyz789",
    "aud": ["auth.tnsvt.com"],
    "exp": 1753108500,
    "iat": 1752503700,
    "jti": "jti_refresh_a1b2c3d4",
    "type": "refresh",
    "family": "token_family_001",
    "device_id": "device_001",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  }
}
```

### 3.3 Claims Obligatorios

| Claim        | Tipo   | Descripción                                         |
|--------------|--------|-----------------------------------------------------|
| `iss`        | string | Emisor del token (Auth Server URL)                  |
| `sub`        | string | Sujeto (user_id o service_id)                       |
| `aud`        | array  | Audiencias válidas                                  |
| `exp`        | int    | Expiración (Unix timestamp)                         |
| `iat`        | int    | Emisión (Unix timestamp)                            |
| `nbf`        | int    | No válido antes de (Unix timestamp)                 |
| `jti`        | string | ID único del token (anti-replay)                    |
| `scope`      | string | Permisos del token (espacio separados)              |
| `roles`      | array  | Roles del usuario/servicio                          |
| `tenant_id`  | string | Tenant asociado (multi-tenant)                      |
| `mfa_verified` | bool | Si 2FA fue verificado                              |
| `device_id`  | string | Dispositivo desde el que se autenticó              |

### 3.4 Validación de Token

```go
type TokenValidator struct {
    publicKey  *rsa.PublicKey
    issuer     string
    audience   []string
    clockSkew  time.Duration
}

func (v *TokenValidator) Validate(tokenStr string) (*Claims, error) {
    token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
        if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
            return nil, fmt.Errorf("método de firma inesperado: %v", t.Header["alg"])
        }
        return v.publicKey, nil
    })
    
    if err != nil {
        return nil, fmt.Errorf("token inválido: %w", err)
    }
    
    claims, ok := token.Claims.(*Claims)
    if !ok || !token.Valid {
        return nil, fmt.Errorf("claims inválidos")
    }
    
    // Validaciones
    if claims.Issuer != v.issuer {
        return nil, fmt.Errorf("issuer inválido")
    }
    
    if !v.containsAudience(claims.Audience) {
        return nil, fmt.Errorf("audiencia inválida")
    }
    
    if claims.ExpiresAt != nil && claims.ExpiresAt.Time.Add(v.clockSkew).Before(time.Now()) {
        return nil, fmt.Errorf("token expirado")
    }
    
    if claims.NotBefore != nil && claims.NotBefore.Time.Add(-v.clockSkew).After(time.Now()) {
        return nil, fmt.Errorf("token aún no válido")
    }
    
    // Verificar que el token no esté en la blacklist (JTI)
    if v.isBlacklisted(claims.ID) {
        return nil, fmt.Errorf("token revocado")
    }
    
    return claims, nil
}
```

---

## 4. RBAC: Matriz de Roles y Permisos

### 4.1 Definición de Roles

| #  | Rol               | Descripción                                    | Nivel   |
|----|-------------------|------------------------------------------------|---------|
| 1  | `super_admin`     | Administrador total del sistema                | Global  |
| 2  | `admin`           | Administrador de plataforma                    | Global  |
| 3  | `trader`          | Trader profesional (acceso completo trading)   | Global  |
| 4  | `viewer`          | Observador de datos de mercado y trading       | Global  |
| 5  | `api_user`        | Usuario con acceso API programático            | Global  |
| 6  | `billing_admin`   | Administrador de facturación                   | Global  |
| 7  | `support`         | Soporte técnico (solo lectura)                 | Global  |
| 8  | `developer`       | Desarrollador (acceso a API, sandbox)          | Global  |
| 9  | `tenant_admin`    | Administrador de un tenant                     | Tenant  |
| 10 | `tenant_trader`   | Trader dentro de un tenant                     | Tenant  |
| 11 | `tenant_viewer`   | Observador dentro de un tenant                 | Tenant  |
| 12 | `bot_service`     | Servicio bot (acceso API limitado)             | Service |

### 4.2 Matriz de Permisos Detallada

| Permiso                          | super_admin | admin | trader | viewer | api_user | billing_admin | support | developer | tenant_admin | tenant_trader | tenant_viewer | bot_service |
|----------------------------------|:-----------:|:-----:|:------:|:------:|:--------:|:-------------:|:-------:|:---------:|:------------:|:-------------:|:-------------:|:-----------:|
| **Trading**                      |             |       |        |        |          |               |         |           |              |               |               |             |
| `trading:read`                   | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `trading:write`                  | ✅          | ✅    | ✅     | ❌     | ✅       | ❌            | ❌      | ✅        | ✅           | ✅            | ❌            | ✅          |
| `trading:cancel`                 | ✅          | ✅    | ✅     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ✅            | ❌            | ❌          |
| `trading:execute`                | ✅          | ✅    | ✅     | ❌     | ✅       | ❌            | ❌      | ✅        | ✅           | ✅            | ❌            | ✅          |
| **Broker**                       |             |       |        |        |          |               |         |           |              |               |               |             |
| `broker:read`                    | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `broker:write`                   | ✅          | ✅    | ✅     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ✅            | ❌            | ✅          |
| `broker:connect`                 | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| `broker:configure`               | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| **Risk**                         |             |       |        |        |          |               |         |           |              |               |               |             |
| `risk:read`                      | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `risk:write`                     | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| `risk:override`                  | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| **AI/ML**                        |             |       |        |        |          |               |         |           |              |               |               |             |
| `ai:read`                        | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `ai:write`                       | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ✅        | ✅           | ❌            | ❌            | ❌          |
| `ai:deploy`                      | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ✅        | ❌           | ❌            | ❌            | ❌          |
| **Platform**                     |             |       |        |        |          |               |         |           |              |               |               |             |
| `platform:read`                  | ✅          | ✅    | ❌     | ❌     | ❌       | ✅            | ✅      | ✅        | ✅           | ❌            | ❌            | ❌          |
| `platform:write`                 | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| `platform:admin`                 | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| `platform:billing`               | ✅          | ❌    | ❌     | ❌     | ❌       | ✅            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| `platform:users`                 | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ✅      | ❌        | ✅           | ❌            | ❌            | ❌          |
| **Notification**                 |             |       |        |        |          |               |         |           |              |               |               |             |
| `notification:read`              | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `notification:write`             | ✅          | ✅    | ✅     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ✅            | ❌            | ✅          |
| `notification:configure`         | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| **Copy Trading**                 |             |       |        |        |          |               |         |           |              |               |               |             |
| `copytrading:read`               | ✅          | ✅    | ✅     | ✅     | ✅       | ❌            | ✅      | ✅        | ✅           | ✅            | ✅            | ✅          |
| `copytrading:write`              | ✅          | ✅    | ✅     | ❌     | ✅       | ❌            | ❌      | ❌        | ✅           | ✅            | ❌            | ❌          |
| `copytrading:manage`             | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ✅           | ❌            | ❌            | ❌          |
| **Audit**                        |             |       |        |        |          |               |         |           |              |               |               |             |
| `audit:read`                     | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ✅      | ✅        | ✅           | ❌            | ❌            | ❌          |
| `audit:export`                   | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| **System**                       |             |       |        |        |          |               |         |           |              |               |               |             |
| `system:config`                  | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| `system:secrets`                 | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |
| `system:logs`                    | ✅          | ✅    | ❌     | ❌     | ❌       | ❌            | ✅      | ✅        | ✅           | ❌            | ❌            | ❌          |
| `system:deploy`                  | ✅          | ❌    | ❌     | ❌     | ❌       | ❌            | ❌      | ❌        | ❌           | ❌            | ❌            | ❌          |

### 4.3 Implementación RBAC

```go
type Permission struct {
    Resource string
    Action   string
}

type RBACConfig struct {
    Roles       map[string][]Permission
    RoleHierarchy map[string][]string  // Roles padre
}

var DefaultRBAC = RBACConfig{
    Roles: map[string][]Permission{
        "super_admin": {
            {Resource: "trading",   Action: "read"},
            {Resource: "trading",   Action: "write"},
            {Resource: "trading",   Action: "cancel"},
            {Resource: "trading",   Action: "execute"},
            {Resource: "broker",    Action: "read"},
            {Resource: "broker",    Action: "write"},
            {Resource: "broker",    Action: "connect"},
            {Resource: "broker",    Action: "configure"},
            {Resource: "risk",      Action: "read"},
            {Resource: "risk",      Action: "write"},
            {Resource: "risk",      Action: "override"},
            {Resource: "ai",        Action: "read"},
            {Resource: "ai",        Action: "write"},
            {Resource: "ai",        Action: "deploy"},
            {Resource: "platform",  Action: "read"},
            {Resource: "platform",  Action: "write"},
            {Resource: "platform",  Action: "admin"},
            {Resource: "platform",  Action: "billing"},
            {Resource: "platform",  Action: "users"},
            {Resource: "notification", Action: "read"},
            {Resource: "notification", Action: "write"},
            {Resource: "notification", Action: "configure"},
            {Resource: "copytrading", Action: "read"},
            {Resource: "copytrading", Action: "write"},
            {Resource: "copytrading", Action: "manage"},
            {Resource: "audit",     Action: "read"},
            {Resource: "audit",     Action: "export"},
            {Resource: "system",    Action: "config"},
            {Resource: "system",    Action: "secrets"},
            {Resource: "system",    Action: "logs"},
            {Resource: "system",    Action: "deploy"},
        },
        "tenant_trader": {
            {Resource: "trading",   Action: "read"},
            {Resource: "trading",   Action: "write"},
            {Resource: "trading",   Action: "cancel"},
            {Resource: "trading",   Action: "execute"},
            {Resource: "broker",    Action: "read"},
            {Resource: "broker",    Action: "write"},
            {Resource: "risk",      Action: "read"},
            {Resource: "ai",        Action: "read"},
            {Resource: "notification", Action: "read"},
            {Resource: "notification", Action: "write"},
            {Resource: "copytrading", Action: "read"},
            {Resource: "copytrading", Action: "write"},
        },
        "bot_service": {
            {Resource: "trading",   Action: "read"},
            {Resource: "trading",   Action: "write"},
            {Resource: "trading",   Action: "execute"},
            {Resource: "broker",    Action: "read"},
            {Resource: "broker",    Action: "write"},
            {Resource: "risk",      Action: "read"},
            {Resource: "ai",        Action: "read"},
            {Resource: "notification", Action: "read"},
            {Resource: "notification", Action: "write"},
            {Resource: "copytrading", Action: "read"},
        },
    },
    RoleHierarchy: map[string][]string{
        "super_admin":  {"admin"},
        "admin":        {"tenant_admin", "support"},
        "tenant_admin": {"tenant_trader"},
        "trader":       {},
        "viewer":       {},
    },
}
```

---

## 5. WAF y Rate Limiting

### 5.1 Reglas WAF (Traefik Middleware)

```yaml
# traefik/middleware/waf.yml
http:
  middlewares:
    waf-rules:
      plugin:
        bouncer:
          enabled: true
          mode: block
          # Reglas OWASP CRS
          crs: true
          # Bloquear SQL injection
          sqlInjection: true
          # Bloquear XSS
          xss: true
          # Bloquear path traversal
          pathTraversal: true
          # Bloquear command injection
          commandInjection: true
          # Bloquear file inclusion
          fileInclusion: true
          # Rate limiting
          rateLimit: false  # Usamos middleware dedicado
          
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        contentSecurityPolicy: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss://*.tnsvt.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"
        permissionsPolicy: "camera=(), microphone=(), geolocation=()"
        customResponseHeaders:
          X-Powered-By: ""
          Server: ""
```

### 5.2 Rate Limiting

| Endpoint              | Per Usuario   | Per IP        | Per API Key   | Ventana  |
|-----------------------|---------------|---------------|---------------|----------|
| `/api/auth/login`     | 5 req/min     | 20 req/min    | N/A           | 1 min    |
| `/api/auth/refresh`   | 10 req/min    | 50 req/min    | N/A           | 1 min    |
| `/api/trading/*`      | 100 req/min   | 500 req/min   | 1000 req/min  | 1 min    |
| `/api/market/*`       | 200 req/min   | 1000 req/min  | 5000 req/min  | 1 min    |
| `/api/ai/*`           | 50 req/min    | 200 req/min   | 500 req/min   | 1 min    |
| `/api/platform/*`     | 100 req/min   | 500 req/min   | 1000 req/min  | 1 min    |
| `/api/webhook/*`      | 30 req/min    | 100 req/min   | 300 req/min   | 1 min    |
| WebSocket connections | 5 simult.     | 20 simult.    | 50 simult.    | N/A      |

**Configuración Traefik Rate Limiting:**

```yaml
# traefik/middleware/ratelimit.yml
http:
  middlewares:
    rate-limit-auth:
      rateLimit:
        average: 5
        burst: 10
        period: 1m
        
    rate-limit-trading:
      rateLimit:
        average: 100
        burst: 200
        period: 1m
        
    rate-limit-market:
      rateLimit:
        average: 200
        burst: 500
        period: 1m
        
    rate-limit-global-ip:
      rateLimit:
        average: 500
        burst: 1000
        period: 1m
```

**Implementación Rate Limiter con Redis:**

```go
type RateLimiter struct {
    redis  *redis.Client
    window time.Duration
}

func (r *RateLimiter) Allow(key string, limit int) (bool, *RateLimitInfo) {
    now := time.Now().UnixMilli()
    windowStart := now - r.window.Milliseconds()
    
    pipe := r.redis.Pipeline()
    
    // Eliminar entradas antiguas
    pipe.ZRemRangeByScore(ctx, key, "0", strconv.FormatInt(windowStart, 10))
    
    // Contar peticiones actuales
    count := pipe.ZCard(ctx, key)
    
    // Agregar petición actual
    pipe.ZAdd(ctx, key, &redis.Z{Score: float64(now), Member: now})
    
    // Establecer TTL
    pipe.Expire(ctx, key, r.window)
    
    results, _ := pipe.Exec(ctx)
    
    currentCount := count.Val()
    
    return currentCount < int64(limit), &RateLimitInfo{
        Limit:     limit,
        Remaining: max(0, limit-int(currentCount)),
        ResetAt:   time.UnixMilli(now + r.window.Milliseconds()),
    }
}
```

---

## 6. Cifrado

### 6.1 En Tránsito (TLS 1.3)

| Componente          | Protocolo  | Certificados         | Renovación |
|---------------------|------------|----------------------|------------|
| Frontend → Traefik  | TLS 1.3    | Let's Encrypt (ACME) | 60 días    |
| Traefik → Backend   | TLS 1.3    | CA interna (Vault)   | 90 días    |
| Inter-servicio      | mTLS 1.3   | CA interna (Vault)   | 90 días    |
| NATS                | TLS 1.3    | CA interna (Vault)   | 90 días    |
| PostgreSQL           | TLS 1.3    | CA interna (Vault)   | 90 días    |
| Redis               | TLS 1.3    | CA interna (Vault)   | 90 días    |

### 6.2 En Reposo (AES-256-GCM)

| Datos                          | Cifrado        | Key Rotation | Almacén                  |
|--------------------------------|----------------|--------------|--------------------------|
| Credenciales de usuario        | AES-256-GCM   | 90 días      | PostgreSQL               |
| API Keys                       | AES-256-GCM   | 90 días      | Vault                    |
| Secretos de configuración      | AES-256-GCM   | 90 días      | Vault / K8s Secrets      |
| Datos financieros              | AES-256-GCM   | 90 días      | PostgreSQL + TimescaleDB |
| Logs sensibles                 | AES-256-GCM   | 90 días      | Loki (encrypted)         |
| Backups                        | AES-256-GCM   | 90 días      | S3 / MinIO               |

### 6.3 Cifrado de Datos de Usuario

```go
type DataEncryptor struct {
    keyProvider KeyProvider
}

func (e *DataEncryptor) EncryptField(plaintext []byte) ([]byte, error) {
    key, err := e.keyProvider.CurrentKey()
    if err != nil {
        return nil, err
    }
    
    block, err := aes.NewCipher(key)
    if err != nil {
        return nil, err
    }
    
    aesGCM, err := cipher.NewGCM(block)
    if err != nil {
        return nil, err
    }
    
    nonce := make([]byte, aesGCM.NonceSize())
    if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
        return nil, err
    }
    
    ciphertext := aesGCM.Seal(nil, nonce, plaintext, nil)
    
    // Formato: version(1) + keyId(4) + nonce(12) + ciphertext
    result := make([]byte, 0, 1+4+12+len(ciphertext))
    result = append(result, 1) // version
    result = append(result, key.ID()...)
    result = append(result, nonce...)
    result = append(result, ciphertext...)
    
    return result, nil
}
```

---

## 7. Gestión de Secretos

### 7.1 Vault (HashiCorp Vault)

```
┌─────────────────────────────────────────────────────────────┐
│                    GESTIÓN DE SECRETOS                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────────┐  │
│  │   Vault     │    │  External   │    │  Sealed Secrets│  │
│  │   Server    │    │  Secrets    │    │  (K8s backup)  │  │
│  │  (prod)     │    │  Operator   │    │                │  │
│  └──────┬──────┘    └──────┬──────┘    └────────┬───────┘  │
│         │                  │                     │          │
│         ▼                  ▼                     ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Kubernetes Secrets                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │db-creds  │ │jwt-keys  │ │api-keys  │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Mount Paths en Vault:**

| Mount Path                | Tipo   | Contenido                                  |
|---------------------------|--------|--------------------------------------------|
| `secret/data/tnsvt/db`   | KV v2  | Credenciales PostgreSQL, Redis             |
| `secret/data/tnsvt/jwt`  | KV v2  | Claves RSA para JWT signing                |
| `secret/data/tnsvt/api`  | KV v2  | API keys de brokers, Telegram, etc.        |
| `secret/data/tnsvt/encrypt` | KV v2 | Claves AES-256 para cifrado de datos      |
| `pki/data/tnsvt`         | PKI    | Certificados y claves privadas internas    |
| `transit/data/tnsvt`     | Transit| Claves de cifrado como servicio            |

---

## 8. Rotación de Claves

### 8.1 Estrategia de Rotación (Ciclo 90 días)

```
┌─────────────────────────────────────────────────────────────┐
│              CICLO DE ROTACIÓN DE CLAVES                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Día 0         Día 80        Día 90        Día 91          │
│    │             │             │             │               │
│    ▼             ▼             ▼             ▼               │
│  ┌─────┐     ┌─────┐      ┌─────┐      ┌─────┐            │
│  │Key  │     │Key  │      │Key  │      │Key  │            │
│  │N    │     │N    │      │N    │      │N+1  │            │
│  │(old)│     │(old)│      │(old)│      │(new)│            │
│  └─────┘     └─────┘      └─────┘      └─────┘            │
│    │             │             │             │               │
│    │          Aviso de      Último día    Rotación         │
│    │          rotación      de válidad    completada        │
│    │                                                              │
│    │  ←────────────────── 90 días ──────────────────►│      │
│    │                          │    ←─ 10 días grace ─►│      │
│                                              │               │
│                                    Token antiguo             │
│                                    sigue válido              │
│                                    durante gracia            │
└─────────────────────────────────────────────────────────────┘
```

| Componente              | Rotación Automática | Alerta Pre-Rotación | Grace Period |
|-------------------------|:-------------------:|:-------------------:|:------------:|
| JWT Signing Keys (RSA)  | ✅                   | 10 días antes       | 10 días      |
| AES-256 Data Keys       | ✅                   | 10 días antes       | 10 días      |
| TLS Certificates (mTLS) | ✅ (ACME/Vault)      | 7 días antes        | 7 días       |
| API Keys (broker)       | ❌ Manual            | 30 días antes       | N/A          |
| Database Passwords      | ✅ (Vault)           | 10 días antes       | 10 días      |
| Encryption at Rest Keys | ✅ (Vault Transit)   | 10 días antes       | 10 días      |

### 8.2 Script de Rotación Automática

```go
type KeyRotationService struct {
    vault     *vault.Client
    notifier  NotificationService
    auditLog  AuditLogWriter
}

func (s *KeyRotationService) RotateJWTKeys() error {
    // 1. Generar nueva clave RSA
    newKey, err := rsa.GenerateKey(rand.Reader, 4096)
    if err != nil {
        return err
    }
    
    // 2. Subir a Vault
    keyID := fmt.Sprintf("jwt-key-%s", time.Now().Format("2006-01-02"))
    if err := s.vault.SetSecret("tnsvt/jwt", keyID, newKey); err != nil {
        return err
    }
    
    // 3. Actualizar configuración del Auth Server
    if err := s.updateAuthServerConfig(keyID); err != nil {
        return err
    }
    
    // 4. Verificar que tokens antiguos siguen válidos durante grace period
    // Los tokens viejos tienen el kid en el header, el server puede verificar ambos
    
    // 5. Auditar rotación
    s.auditLog.Write(AuditEvent{
        Action:    "key.rotation.jwt",
        Details:   map[string]interface{}{"new_key_id": keyID},
        Timestamp: time.Now(),
    })
    
    // 6. Notificar a admins
    s.notifier.Send(Notification{
        Severity: "info",
        Message:  fmt.Sprintf("Rotación de JWT keys completada. Nuevo key ID: %s", keyID),
    })
    
    return nil
}
```

---

## 9. Audit Logs Inmutables

### 9.1 Estructura de Audit Log

```json
{
  "seq": 1,
  "prev_hash": "a1b2c3d4e5f6...",
  "hash": "f6e5d4c3b2a1...",
  "timestamp": "2026-07-14T10:30:00.000Z",
  "event_type": "trading.order.executed",
  "actor": {
    "type": "user",
    "id": "user_xyz789",
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "order",
    "id": "ORD-20260714-001"
  },
  "action": "execute",
  "result": "success",
  "details": {
    "symbol": "EURUSD",
    "quantity": 1.0,
    "price": 1.0842,
    "broker": "MT5"
  },
  "metadata": {
    "tenant_id": "tenant_abc123",
    "request_id": "req-123",
    "trace_id": "4bf92f3577b34da6a6ce93a30f8e2b0a"
  }
}
```

### 9.2 Cadena de Hash

```
┌─────────┐    hash    ┌─────────┐    hash    ┌─────────┐
│  Log 1  │───────────►│  Log 2  │───────────►│  Log 3  │
│         │            │         │            │         │
│ seq: 1  │            │ seq: 2  │            │ seq: 3  │
│ prev: 0 │            │ prev: h1│            │ prev: h2│
│ hash: h1│            │ hash: h2│            │ hash: h3│
└─────────┘            └─────────┘            └─────────┘
     │                      │                      │
     ▼                      ▼                      ▼
 Verificación            Verificación          Verificación
 de integridad           de integridad         de integridad
```

### 9.3 Implementación

```go
type ImmutableAuditLog struct {
    mu          sync.Mutex
    db          *sql.DB
    prevHash    string
    chainHeight int64
}

func (a *ImmutableAuditLog) Write(event AuditEvent) error {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    // 1. Serializar evento
    data, err := json.Marshal(event)
    if err != nil {
        return err
    }
    
    // 2. Calcular hash: SHA256(prev_hash + seq + data)
    a.chainHeight++
    hashInput := fmt.Sprintf("%s:%d:%s", a.prevHash, a.chainHeight, string(data))
    hash := sha256.Sum256([]byte(hashInput))
    hashHex := hex.EncodeToString(hash[:])
    
    // 3. Insertar en append-only table (sin UPDATE/DELETE habilitados)
    _, err = a.db.Exec(`
        INSERT INTO audit_log (seq, prev_hash, hash, event_data, created_at)
        VALUES ($1, $2, $3, $4, $5)
    `, a.chainHeight, a.prevHash, hashHex, data, time.Now())
    
    if err != nil {
        return err
    }
    
    a.prevHash = hashHex
    return nil
}

func (a *ImmutableAuditLog) VerifyIntegrity(fromSeq, toSeq int64) error {
    rows, err := a.db.Query(`
        SELECT seq, prev_hash, hash, event_data 
        FROM audit_log 
        WHERE seq BETWEEN $1 AND $2 
        ORDER BY seq ASC
    `, fromSeq, toSeq)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    var prevHash string
    var expectedSeq int64
    
    for rows.Next() {
        var seq int64
        var storedPrev, storedHash string
        var eventData []byte
        
        if err := rows.Scan(&seq, &storedPrev, &storedHash, &eventData); err != nil {
            return err
        }
        
        // Verificar secuencia
        if seq != expectedSeq+1 {
            return fmt.Errorf("secuencia rota en seq=%d, esperado=%d", seq, expectedSeq+1)
        }
        
        // Verificar hash previo
        if storedPrev != prevHash {
            return fmt.Errorf("hash previo inválido en seq=%d", seq)
        }
        
        // Verificar hash actual
        hashInput := fmt.Sprintf("%s:%d:%s", storedPrev, seq, string(eventData))
        computedHash := sha256.Sum256([]byte(hashInput))
        computedHex := hex.EncodeToString(computedHash[:])
        
        if computedHex != storedHash {
            return fmt.Errorf("hash de integridad fallido en seq=%d", seq)
        }
        
        prevHash = storedHash
        expectedSeq = seq
    }
    
    return nil
}
```

---

## 10. Protección Anti-Replay y Anti-Fraude

### 10.1 Anti-Replay

```go
type AntiReplay struct {
    redis     *redis.Client
    ttl       time.Duration  // 5 minutos
    nonceSize int            // 32 bytes
}

func (a *AntiReplay) Validate(nonce string, timestamp int64) error {
    // 1. Verificar timestamp (± 5 minutos)
    now := time.Now().Unix()
    if abs(now-timestamp) > 300 {
        return ErrTimestampExpired
    }
    
    // 2. Verificar nonce único
    key := fmt.Sprintf("nonce:%s", nonce)
    exists, _ := a.redis.Exists(ctx, key).Result()
    if exists > 0 {
        return ErrNonceReused
    }
    
    // 3. Almacenar nonce con TTL
    a.redis.Set(ctx, key, "1", a.ttl)
    
    return nil
}
```

### 10.2 Anti-Fraude

| Regla                          | Umbral                    | Acción              |
|--------------------------------|---------------------------|---------------------|
| Velocidad de órdenes           | > 10 órdenes/min          | Bloquear + alertar  |
| Tamaño de posición             | > 10% del equity          | Bloquear + alertar  |
| Cambio de IP durante sesión    | > 2 cambios en 1 hora     | Alertar al soporte  |
| Login desde país inusual       | Primer login desde país   | Requiere 2FA        |
| Intentos de login fallidos     | > 5 en 15 minutos        | Bloquear 30 min     |
| Withdrawal inusual             | > 50% del balance mensual | Revisión manual     |
| Patrón de trading anómalo      | > 3σ del histórico       | Alertar             |

### 10.3 Implementación Anti-Fraude

```go
type AntiFraudEngine struct {
    redis          *redis.Client
    alertService   AlertService
    rules          []FraudRule
}

type FraudRule struct {
    Name      string
    Window    time.Duration
    Threshold int
    Action    FraudAction
}

type FraudAction int

const (
    FraudAlert FraudAction = iota
    FraudBlock
    FraudRequireReview
)

func (a *AntiFraudEngine) CheckTransaction(tx Transaction) ([]FraudAlert, error) {
    var alerts []FraudAlert
    
    for _, rule := range a.rules {
        count, err := a.getEventCount(tx.UserID, rule.Name, rule.Window)
        if err != nil {
            continue
        }
        
        if count >= rule.Threshold {
            alert := FraudAlert{
                Rule:     rule.Name,
                UserID:   tx.UserID,
                Count:    count,
                Threshold: rule.Threshold,
                Action:   rule.Action,
                Timestamp: time.Now(),
            }
            alerts = append(alerts, alert)
            
            switch rule.Action {
            case FraudBlock:
                a.blockUser(tx.UserID, rule.Name)
            case FraudAlert:
                a.alertService.SendAlert(alert)
            case FraudRequireReview:
                a.flagForReview(tx)
            }
        }
    }
    
    return alerts, nil
}
```

---

## 11. 2FA (TOTP)

### Flujo de Autenticación 2FA

```
┌──────────┐                ┌──────────┐                ┌──────────┐
│  Client  │                │  Auth    │                │  Totp    │
│          │                │  Server  │                │  Store   │
└────┬─────┘                └────┬─────┘                └────┬─────┘
     │                           │                           │
     │ 1. POST /auth/login       │                           │
     │   (email, password)       │                           │
     │──────────────────────────►│                           │
     │                           │  2. Verificar password    │
     │                           │──────────────────────────►│
     │                           │◄──────────────────────────│
     │                           │                           │
     │                           │  3. ¿2FA habilitado?      │
     │                           │     Sí → crear challenge  │
     │  4. 200 {challenge_id,   │                           │
     │     requires_2fa: true}  │                           │
     │◄──────────────────────────│                           │
     │                           │                           │
     │ 5. POST /auth/2fa/verify │                           │
     │   (challenge_id, code)   │                           │
     │──────────────────────────►│                           │
     │                           │  6. Verificar TOTP code   │
     │                           │──────────────────────────►│
     │                           │◄──────────────────────────│
     │                           │                           │
     │  7. 200 {access_token,   │                           │
     │     refresh_token}        │                           │
     │◄──────────────────────────│                           │
     │                           │                           │
```

### Setup 2FA

```
┌──────────┐                ┌──────────┐
│  Client  │                │  Auth    │
│          │                │  Server  │
└────┬─────┘                └────┬─────┘
     │                           │
     │ 1. POST /auth/2fa/setup  │
     │──────────────────────────►│
     │                           │  2. Generar secret TOTP
     │                           │     (32 bytes, Base32)
     │                           │
     │  3. {secret, otpauth_url} │
     │◄──────────────────────────│
     │                           │
     │ 4. Usuario escanea QR    │
     │    con authenticator app  │
     │                           │
     │ 5. POST /auth/2fa/enable │
     │   (secret, code)         │
     │──────────────────────────►│
     │                           │  6. Verificar code contra secret
     │                           │
     │  7. {recovery_codes: [...]}│
     │◄──────────────────────────│
     │                           │
```

---

## 12. Políticas CORS y CSP

### 12.1 CORS Policy

```yaml
# traefik/middleware/cors.yml
http:
  middlewares:
    cors-policy:
      headers:
        accessControlAllowMethods:
          - GET
          - POST
          - PUT
          - PATCH
          - DELETE
          - OPTIONS
        accessControlAllowHeaders:
          - Authorization
          - Content-Type
          - X-Request-ID
          - X-Correlation-ID
          - X-Tenant-ID
          - X-Device-ID
        accessControlAllowOriginList:
          - "https://app.tnsvt.com"
          - "https://staging.tnsvt.com"
          - "http://localhost:3000"  # Solo desarrollo
        accessControlExposeHeaders:
          - X-RateLimit-Limit
          - X-RateLimit-Remaining
          - X-RateLimit-Reset
          - X-Request-ID
        accessControlMaxAge: 86400
        accessControlAllowCredentials: true
```

### 12.2 Content Security Policy

```
default-src 'self';
script-src 'self' 'wasm-unsafe-eval' 'strict-dynamic';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self' wss://*.tnsvt.com https://api.tnsvt.com;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
object-src 'none';
media-src 'none';
worker-src 'blob:;
manifest-src 'self';
upgrade-insecure-requests;
```

### 12.3 Headers de Seguridad Completos

| Header                          | Valor                                               |
|---------------------------------|-----------------------------------------------------|
| `Strict-Transport-Security`    | `max-age=31536000; includeSubDomains; preload`      |
| `X-Content-Type-Options`       | `nosniff`                                           |
| `X-Frame-Options`              | `DENY`                                              |
| `X-XSS-Protection`             | `1; mode=block`                                     |
| `Referrer-Policy`              | `strict-origin-when-cross-origin`                   |
| `Permissions-Policy`           | `camera=(), microphone=(), geolocation=()`          |
| `Content-Security-Policy`      | (ver arriba)                                        |
| `X-Permitted-Cross-Domain-Policies` | `none`                                         |
| `Cross-Origin-Opener-Policy`   | `same-origin`                                       |
| `Cross-Origin-Resource-Policy` | `same-origin`                                       |
| `Cross-Origin-Embedder-Policy` | `require-corp`                                      |

---

**Fin del documento 06 — Seguridad**
