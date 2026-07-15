package middleware

import "os"

func getEnvImpl(key string) string {
	return os.Getenv(key)
}