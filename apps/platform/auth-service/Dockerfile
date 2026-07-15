# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - auth-service
# Multi-stage build optimizado para Go
# ═══════════════════════════════════════════════════════════════

# ─── Stage 1: Build ────────────────────────────────────────────
FROM golang:1.22-alpine AS builder

WORKDIR /build

# Instalar git para go modules
RUN apk add --no-cache git ca-certificates

# Copiar shared-go primero (mejor cache layer)
COPY shared/go-common /build/shared/go-common
COPY shared/proto /build/shared/proto

# Copiar go.mod y descargar deps
COPY apps/platform/auth-service/go.mod apps/platform/auth-service/go.sum* ./
RUN go mod download

# Copiar el resto del código
COPY apps/platform/auth-service/ ./

# Build
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s" \
    -o /build/bin/auth-service \
    .

# ─── Stage 2: Runtime ──────────────────────────────────────────
FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata curl
RUN adduser -D -u 1000 tnsvt && \
    addgroup -g 1000 tnsvt tnsvt

WORKDIR /app

# Copiar binario
COPY --from=builder /build/bin/auth-service /app/auth-service

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD curl -fsS http://localhost:8001/health || exit 1

# Non-root user
USER tnsvt

# Expose port
EXPOSE 8001

# Run
ENTRYPOINT ["/app/auth-service"]