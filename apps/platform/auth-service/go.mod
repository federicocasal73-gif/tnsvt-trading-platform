module github.com/tnsvt/auth-service

go 1.22

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/golang-jwt/jwt/v5 v5.2.1
	github.com/google/uuid v1.6.0
	github.com/jackc/pgx/v5 v5.6.0
	github.com/prometheus/client_golang v1.19.1
	github.com/redis/go-redis/v9 v9.5.1
	golang.org/x/crypto v0.23.0

	github.com/tnsvt/shared-go v0.0.0
)

replace github.com/tnsvt/shared-go => ../../../shared/go-common