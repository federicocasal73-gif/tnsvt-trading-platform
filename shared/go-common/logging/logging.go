// Package logging implementa logging estructurado con secret masking.
// Portado de signal_copier/log_security.py a Go.
package logging

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"strings"
)

// Secret keys que se enmascaran automáticamente
var defaultSecretKeys = []string{
	"password",
	"passwd",
	"secret",
	"token",
	"api_key",
	"apikey",
	"private_key",
	"authorization",
	"jwt",
	"bearer",
	"mt5_password",
	"bot_token",
	"telegram_token",
}

// Logger es un wrapper sobre slog con secret masking
type Logger struct {
	underlying *slog.Logger
	masker     *SecretMasker
}

// SecretMasker enmascara secrets en strings
type SecretMasker struct {
	patterns []*regexp.Regexp
}

// NewSecretMasker crea un nuevo masker con patterns por defecto
func NewSecretMasker() *SecretMasker {
	sm := &SecretMasker{}
	for _, key := range defaultSecretKeys {
		// Pattern: key=value, key: value, "key":"value"
		pattern := fmt.Sprintf(`(?i)(%s["']?\s*[:=]\s*["']?)([^"'\s,}]+)`, regexp.QuoteMeta(key))
		sm.patterns = append(sm.patterns, regexp.MustCompile(pattern))
	}
	return sm
}

// Mask aplica masking al texto
func (sm *SecretMasker) Mask(text string) string {
	for _, p := range sm.patterns {
		text = p.ReplaceAllString(text, "${1}***MASKED***")
	}
	return text
}

// MaskMap enmascara secrets en un map
func (sm *SecretMasker) MaskMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		lower := strings.ToLower(k)
		isSecret := false
		for _, secretKey := range defaultSecretKeys {
			if strings.Contains(lower, secretKey) {
				isSecret = true
				break
			}
		}
		if isSecret {
			out[k] = "***MASKED***"
		} else {
			out[k] = v
		}
	}
	return out
}

// New crea un nuevo logger
func New(serviceName, level string) *Logger {
	var lvl slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lvl = slog.LevelDebug
	case "info":
		lvl = slog.LevelInfo
	case "warn", "warning":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}

	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: lvl,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			// Enmascarar secrets en atributos
			lowerKey := strings.ToLower(a.Key)
			for _, secretKey := range defaultSecretKeys {
				if strings.Contains(lowerKey, secretKey) {
					return slog.String(a.Key, "***MASKED***")
				}
			}
			return a
		},
	})

	return &Logger{
		underlying: slog.New(handler).With("service", serviceName),
		masker:     NewSecretMasker(),
	}
}

// WithContext retorna un logger con contexto
func (l *Logger) WithContext(ctx context.Context) *Logger {
	return &Logger{
		underlying: l.underlying.With("trace_id", getTraceID(ctx)),
		masker:     l.masker,
	}
}

// WithFields retorna un logger con campos adicionales
func (l *Logger) WithFields(fields map[string]any) *Logger {
	masked := l.masker.MaskMap(fields)
	attrs := make([]any, 0, len(masked)*2)
	for k, v := range masked {
		attrs = append(attrs, k, v)
	}
	return &Logger{
		underlying: l.underlying.With(attrs...),
		masker:     l.masker,
	}
}

// Debug log debug
func (l *Logger) Debug(msg string, args ...any) {
	l.underlying.Debug(fmt.Sprintf(msg, args...))
}

// Info log info
func (l *Logger) Info(msg string, args ...any) {
	l.underlying.Info(msg, args...)
}

// Warn log warning
func (l *Logger) Warn(msg string, args ...any) {
	l.underlying.Warn(msg, args...)
}

// Error log error
func (l *Logger) Error(msg string, err error, args ...any) {
	attrs := append(args, "error", err.Error())
	l.underlying.Error(msg, attrs...)
}

func getTraceID(ctx context.Context) string {
	if v := ctx.Value("trace_id"); v != nil {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}