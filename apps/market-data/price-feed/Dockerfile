# ─── Build stage ─────────────────────────────────────────────
FROM golang:1.22-alpine AS build

WORKDIR /src

# Copy shared lib first (replace directive)
COPY shared/go-common/ /src/shared/go-common/

# Copy service
COPY apps/market-data/price-feed/ /src/

# Resolve dependencies (cached if go.mod/go.sum unchanged)
WORKDIR /src
RUN go mod download

# Build static binary
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/price-feed .

# ─── Runtime stage ───────────────────────────────────────────
FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata && \
    adduser -D -u 1000 tnsvt

COPY --from=build /out/price-feed /usr/local/bin/price-feed

USER tnsvt

EXPOSE 8300

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8300/health || exit 1

ENTRYPOINT ["/usr/local/bin/price-feed"]