module github.com/tnsvt/signal-engine

go 1.22

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/google/uuid v1.6.0
	github.com/nats-io/nats.go v1.34.0
	github.com/prometheus/client_golang v1.19.1
	github.com/redis/go-redis/v9 v9.5.1
	github.com/jackc/pgx/v5 v5.6.0

	github.com/tnsvt/shared-go v0.0.0
)

replace github.com/tnsvt/shared-go => ../../../shared/go-common