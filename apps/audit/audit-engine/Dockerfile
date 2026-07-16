# TNSVT V2 - audit-engine
FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache git ca-certificates

COPY shared/go-common /build/shared/go-common
COPY shared/proto /build/shared/proto

COPY apps/audit/audit-engine/go.mod apps/audit/audit-engine/go.sum* ./
RUN go mod download

COPY apps/audit/audit-engine/ ./
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s" \
    -o /build/bin/audit-engine .

FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata curl
RUN adduser -D -u 1000 tnsvt && addgroup -g 1000 tnsvt tnsvt

WORKDIR /app

COPY --from=builder /build/bin/audit-engine /app/audit-engine

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -fsS http://localhost:8600/health || exit 1

USER tnsvt

EXPOSE 8600

ENTRYPOINT ["/app/audit-engine"]
