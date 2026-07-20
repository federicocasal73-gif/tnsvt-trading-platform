// Package config carga la configuración de servicios del gateway.
package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// ServiceConfig configuración de un servicio destino
type ServiceConfig struct {
	Name       string   `json:"name"`        // ej: "auth-service"
	PathPrefix string   `json:"path_prefix"` // ej: "/api/v1/auth"
	Instances  []string `json:"instances"`   // ej: ["http://auth-service:8001"]
	Timeout    int      `json:"timeout_ms"`  // request timeout en ms
	RateLimit  int      `json:"rate_limit"`  // requests por minuto
	HealthPath string   `json:"health_path"` // ej: "/health"
	Required   bool     `json:"required"`    // si es requerido para /health/full
}

// LoadServices carga la configuración desde archivo JSON
// Si el archivo no existe, retorna config por defecto
func LoadServices(path string) []ServiceConfig {
	defaultCfg := []ServiceConfig{
		{
			Name:       "auth-service",
			PathPrefix: "/api/v1/auth",
			Instances:  []string{"http://localhost:8001"},
			Timeout:    5000,
			RateLimit:  100,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "user-service",
			PathPrefix: "/api/v1/users",
			Instances:  []string{"http://localhost:8401"},
			Timeout:    5000,
			RateLimit:  100,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "signal-engine",
			PathPrefix: "/api/v1/signals",
			Instances:  []string{"http://localhost:8003"},
			Timeout:    10000,
			RateLimit:  200,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "execution-engine",
			PathPrefix: "/api/v1/executions",
			Instances:  []string{"http://localhost:8004"},
			Timeout:    30000,
			RateLimit:  100,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "copy-trading",
			PathPrefix: "/api/v1/copy",
			Instances:  []string{"http://localhost:8005"},
			Timeout:    15000,
			RateLimit:  50,
			HealthPath: "/health",
			Required:   false,
		},
		{
			Name:       "risk-engine",
			PathPrefix: "/api/v1/risk",
			Instances:  []string{"http://localhost:8006"},
			Timeout:    5000,
			RateLimit:  200,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "mt5-connector",
			PathPrefix: "/api/v1/brokers",
			Instances:  []string{"http://localhost:8007"},
			Timeout:    15000,
			RateLimit:  100,
			HealthPath: "/health",
			Required:   false,
		},
		{
			Name:       "audit-engine",
			PathPrefix: "/api/v1/audit",
			Instances:  []string{"http://localhost:8600"},
			Timeout:    5000,
			RateLimit:  200,
			HealthPath: "/health",
			Required:   true,
		},
		{
			Name:       "ai-core",
			PathPrefix: "/api/v1/ai",
			Instances:  []string{"http://localhost:8200"},
			Timeout:    30000,
			RateLimit:  50,
			HealthPath: "/health",
			Required:   false,
		},
		{
			Name:       "price-feed",
			PathPrefix: "/api/v1/prices",
			Instances:  []string{"http://localhost:8300"},
			Timeout:    5000,
			RateLimit:  300,
			HealthPath: "/health",
			Required:   false,
		},
		{
			Name:       "telegram-bot-service",
			PathPrefix: "/api/v1/notify",
			Instances:  []string{"http://localhost:8503"},
			Timeout:    10000,
			RateLimit:  100,
			HealthPath: "/health",
			Required:   false,
		},
	}

	// Intentar cargar desde archivo
	if path == "" {
		return defaultCfg
	}

	absPath, _ := filepath.Abs(path)
	data, err := os.ReadFile(absPath)
	if err != nil {
		// Archivo no existe, usar defaults
		return defaultCfg
	}

	var cfg []ServiceConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		// JSON inválido, usar defaults
		return defaultCfg
	}

	return cfg
}