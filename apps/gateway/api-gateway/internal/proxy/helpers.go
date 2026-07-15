package proxy

import (
	"encoding/json"

	"github.com/redis/go-redis/v9"
)

func jsonMarshalImpl(v any) ([]byte, error) {
	return json.Marshal(v)
}

// Redis helpers kept here to avoid adding too many small files
var _ = redis.NoKeys