package source

import (
	"time"

	"github.com/tnsvt/price-feed/internal/models"
)

// nopLogger is a no-op implementation of Logger for tests.
type nopLogger struct{}

func (nopLogger) Info(string, ...any)         {}
func (nopLogger) Warn(string, ...any)         {}
func (nopLogger) Error(string, error, ...any) {}

// newTestStore returns a TickStore with no Redis backend.
func newTestStore() *models.TickStore {
	return models.NewTickStore(nil, time.Minute)
}

// contains is a local copy of the publisher.contains helper, scoped to this package's tests.
func contains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}