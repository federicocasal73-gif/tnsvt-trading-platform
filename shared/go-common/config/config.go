// Package config carga configuración desde .env y variables de entorno.
// Portado de config/settings.py a Go.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config contiene toda la configuración del servicio
type Config struct {
	ServiceName string
	Env         string
	LogLevel    string

	// PostgreSQL
	Postgres PostgresConfig

	// Redis
	Redis RedisConfig

	// NATS
	NATS NATSConfig

	// Ollama
	Ollama OllamaConfig

	// Auth
	Auth AuthConfig

	// Service-specific
	Custom map[string]string
}

// PostgresConfig configuración PostgreSQL
type PostgresConfig struct {
	Host            string
	Port            int
	Database        string
	User            string
	Password        string
	MaxConnections  int
	SSLMode         string
	MigrationPath   string
}

// DSN retorna el connection string
func (p PostgresConfig) DSN() string {
	return fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		p.Host, p.Port, p.User, p.Password, p.Database, p.SSLMode,
	)
}

// RedisConfig configuración Redis
type RedisConfig struct {
	Host     string
	Port     int
	Password string
	DB       int
	MaxConns int
}

// Addr retorna host:port
func (r RedisConfig) Addr() string {
	return fmt.Sprintf("%s:%d", r.Host, r.Port)
}

// NATSConfig configuración NATS
type NATSConfig struct {
	Host        string
	Port        int
	ClusterName string
	MaxPayload  string
}

// URL retorna nats://host:port
func (n NATSConfig) URL() string {
	return fmt.Sprintf("nats://%s:%d", n.Host, n.Port)
}

// OllamaConfig configuración Ollama
type OllamaConfig struct {
	Host  string
	Port  int
	Model string
}

// URL retorna http://host:port
func (o OllamaConfig) URL() string {
	return fmt.Sprintf("http://%s:%d", o.Host, o.Port)
}

// AuthConfig configuración autenticación
type AuthConfig struct {
	JWTSecret             string
	JWTAccessTokenExpire  time.Duration
	JWTRefreshTokenExpire time.Duration
	JWTAlgorithm          string
	BCryptRounds          int
	SessionTimeout        time.Duration
	MaxLoginAttempts      int
	LockoutDuration       time.Duration
}

// Load carga configuración desde variables de entorno
func Load(serviceName string) *Config {
	cfg := &Config{
		ServiceName: serviceName,
		Env:         getEnv("ENV", "development"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
		Custom:      make(map[string]string),
	}

	cfg.Postgres = PostgresConfig{
		Host:           getEnv("POSTGRES_HOST", "localhost"),
		Port:           getEnvInt("POSTGRES_PORT", 5432),
		Database:       getEnv("POSTGRES_DB", "tnsvt"),
		User:           getEnv("POSTGRES_USER", "tnsvt"),
		Password:       getEnv("POSTGRES_PASSWORD", ""),
		MaxConnections: getEnvInt("POSTGRES_MAX_CONNECTIONS", 200),
		SSLMode:        getEnv("POSTGRES_SSLMODE", "disable"),
		MigrationPath:  getEnv("POSTGRES_MIGRATION_PATH", "./migrations"),
	}

	cfg.Redis = RedisConfig{
		Host:     getEnv("REDIS_HOST", "localhost"),
		Port:     getEnvInt("REDIS_PORT", 6379),
		Password: getEnv("REDIS_PASSWORD", ""),
		DB:       getEnvInt("REDIS_DB", 0),
		MaxConns: getEnvInt("REDIS_MAX_CONNECTIONS", 50),
	}

	cfg.NATS = NATSConfig{
		Host:        getEnv("NATS_HOST", "localhost"),
		Port:        getEnvInt("NATS_PORT", 4222),
		ClusterName: getEnv("NATS_CLUSTER_NAME", "tnsvt-cluster"),
		MaxPayload:  getEnv("NATS_MAX_PAYLOAD", "10MB"),
	}

	cfg.Ollama = OllamaConfig{
		Host:  getEnv("OLLAMA_HOST", "localhost"),
		Port:  getEnvInt("OLLAMA_PORT", 11434),
		Model: getEnv("OLLAMA_MODEL", "llama3:8b"),
	}

	cfg.Auth = AuthConfig{
		JWTSecret:             getEnv("JWT_SECRET", ""),
		JWTAccessTokenExpire:  time.Duration(getEnvInt("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)) * time.Minute,
		JWTRefreshTokenExpire: time.Duration(getEnvInt("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)) * 24 * time.Hour,
		JWTAlgorithm:          getEnv("JWT_ALGORITHM", "HS256"),
		BCryptRounds:          getEnvInt("BCRYPT_ROUNDS", 12),
		SessionTimeout:        time.Duration(getEnvInt("SESSION_TIMEOUT_HOURS", 1)) * time.Hour,
		MaxLoginAttempts:      getEnvInt("MAX_LOGIN_ATTEMPTS", 5),
		LockoutDuration:       time.Duration(getEnvInt("LOCKOUT_DURATION_SECONDS", 60)) * time.Second,
	}

	// Cargar resto de variables en Custom para acceso específico del servicio
	for _, env := range os.Environ() {
		if idx := strings.Index(env, "="); idx > 0 {
			key := env[:idx]
			// Ignorar variables ya mapeadas
			if isMapped(key) {
				continue
			}
			cfg.Custom[key] = env[idx+1:]
		}
	}

	return cfg
}

// Get retorna un valor custom con default
func (c *Config) Get(key, defaultValue string) string {
	if v, ok := c.Custom[key]; ok && v != "" {
		return v
	}
	return defaultValue
}

// GetInt retorna un valor custom como int
func (c *Config) GetInt(key string, defaultValue int) int {
	if v, ok := c.Custom[key]; ok && v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return defaultValue
}

// GetFloat retorna un valor custom como float64
func (c *Config) GetFloat(key string, defaultValue float64) float64 {
	if v, ok := c.Custom[key]; ok && v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return defaultValue
}

// GetBool retorna un valor custom como bool
func (c *Config) GetBool(key string, defaultValue bool) bool {
	if v, ok := c.Custom[key]; ok && v != "" {
		b, err := strconv.ParseBool(v)
		if err == nil {
			return b
		}
	}
	return defaultValue
}

// ─── Helpers ───

func getEnv(key, defaultValue string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return defaultValue
}

func isMapped(key string) bool {
	mapped := []string{
		"ENV", "LOG_LEVEL",
		"POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER",
		"POSTGRES_PASSWORD", "POSTGRES_MAX_CONNECTIONS", "POSTGRES_SSLMODE",
		"POSTGRES_MIGRATION_PATH",
		"REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB", "REDIS_MAX_CONNECTIONS",
		"NATS_HOST", "NATS_PORT", "NATS_CLUSTER_NAME", "NATS_MAX_PAYLOAD",
		"OLLAMA_HOST", "OLLAMA_PORT", "OLLAMA_MODEL",
		"JWT_SECRET", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
		"JWT_ALGORITHM", "BCRYPT_ROUNDS", "SESSION_TIMEOUT_HOURS",
		"MAX_LOGIN_ATTEMPTS", "LOCKOUT_DURATION_SECONDS",
	}
	for _, m := range mapped {
		if key == m {
			return true
		}
	}
	return false
}