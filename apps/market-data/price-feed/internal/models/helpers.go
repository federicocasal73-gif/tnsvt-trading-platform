package models

import (
	"context"
	"encoding/json"
	"time"
)

// contextWithTimeout returns a context with a short deadline suitable for cache writes.
func contextWithTimeout() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), 2*time.Second)
}

// jsonMarshal is a thin wrapper to keep the JSON marshalling site explicit.
func jsonMarshal(v any) ([]byte, error) {
	return json.Marshal(v)
}