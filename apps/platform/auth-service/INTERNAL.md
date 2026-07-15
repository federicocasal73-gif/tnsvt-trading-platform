# Auth Service

OAuth2 + JWT + RBAC service for TNSVT V2.

## Stack

- Go 1.22+
- Gin (HTTP framework)
- pgx (PostgreSQL driver)
- golang-jwt (JWT)
- bcrypt (password hashing)
- Redis (rate limiting)

## Quick Start

```bash
# Install dependencies
go mod tidy

# Run
go run main.go
```

Service starts on port 8001 by default.