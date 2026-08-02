// Package cors provides a shared CORS helper that reads allowed origins
// from the CORS_ALLOWED_ORIGINS env var (comma-separated). If unset,
// uses sensible dev defaults.
package cors

import (
	"os"
	"strings"
)

// AllowedOrigins returns the set of allowed CORS origins.
// Read from env var CORS_ALLOWED_ORIGINS (comma-separated).
// Falls back to dev defaults if not set.
func AllowedOrigins() map[string]bool {
	defaults := []string{
		"http://localhost:3000",     // Next.js dev
		"http://localhost:3001",     // Vite dev
		"http://localhost:8501",     // Dashboard
		"http://127.0.0.1:3000",
		"http://127.0.0.1:8501",
		"tauri://localhost",         // Tauri desktop
		"https://app.tnsvt.io",
		"https://dashboard.tnsvt.io",
	}
	if v := os.Getenv("CORS_ALLOWED_ORIGINS"); v != "" {
		defaults = strings.Split(v, ",")
	}
	allowed := make(map[string]bool, len(defaults))
	for _, o := range defaults {
		allowed[strings.TrimSpace(o)] = true
	}
	return allowed
}
