# TNSVT V2 - account-manager
FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache git ca-certificates

COPY shared/go-common /build/shared/go-common
COPY shared/proto /build/shared/proto 2>/dev/null || true

COPY apps/platform/account-manager/go.mod apps/platform/account-manager/go.sum* ./
RUN go mod download

COPY apps/platform/account-manager/ ./
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s" \
    -o /build/bin/account-manager .

FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata curl
RUN adduser -D -u 1000 tnsvt && addgroup -g 1000 tnsvt tnsvt

WORKDIR /app

COPY --from=builder /build/bin/account-manager /app/account-manager

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -fsS http://localhost:8510/health || exit 1

USER tnsvt

EXPOSE 8510

ENTRYPOINT ["/app/account-manager"]
