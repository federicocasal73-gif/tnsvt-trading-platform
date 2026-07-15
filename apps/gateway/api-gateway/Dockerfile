# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - api-gateway
# Multi-stage build para Go
# ═══════════════════════════════════════════════════════════════

FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache git ca-certificates

# Copiar shared-go
COPY shared/go-common /build/shared/go-common
COPY shared/proto /build/shared/proto

# Deps
COPY apps/gateway/api-gateway/go.mod apps/gateway/api-gateway/go.sum* ./
RUN go mod download

# Build
COPY apps/gateway/api-gateway/ ./
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s" \
    -o /build/bin/api-gateway .

# ─── Runtime ───────────────────────────────────────────────────
FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata curl
RUN adduser -D -u 1000 tnsvt && addgroup -g 1000 tnsvt tnsvt

WORKDIR /app

COPY --from=builder /build/bin/api-gateway /app/api-gateway
COPY --from=builder /build/apps/gateway/api-gateway/config /app/config

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD curl -fsS http://localhost:8000/health || exit 1

USER tnsvt

EXPOSE 8000

ENTRYPOINT ["/app/api-gateway"]