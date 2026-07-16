# TNSVT V2 - user-service
FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache git ca-certificates

COPY shared/go-common /build/shared/go-common
COPY shared/proto /build/shared/proto

COPY apps/platform/user-service/go.mod apps/platform/user-service/go.sum* ./
RUN go mod download

COPY apps/platform/user-service/ ./
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s" \
    -o /build/bin/user-service .

FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata curl
RUN adduser -D -u 1000 tnsvt && addgroup -g 1000 tnsvt tnsvt

WORKDIR /app

COPY --from=builder /build/bin/user-service /app/user-service

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -fsS http://localhost:8401/health || exit 1

USER tnsvt

EXPOSE 8401

ENTRYPOINT ["/app/user-service"]
