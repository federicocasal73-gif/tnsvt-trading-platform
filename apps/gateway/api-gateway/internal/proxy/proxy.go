// Package proxy implementa el reverse proxy + service registry + load balancing.
package proxy

import (
	"context"
	"net/http"
	"net/http/httputil"
	"net/url"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/api-gateway/internal/config"
)

// ─── Service Registry ──────────────────────────────────────────

// ServiceRegistry mantiene el estado de todos los microservicios
type ServiceRegistry struct {
	mu       sync.RWMutex
	services map[string]*ServiceState
	log      interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// ServiceState estado runtime de un servicio
type ServiceState struct {
	Config         config.ServiceConfig
	Instances      []*InstanceState
	CurrentCounter atomic.Uint64 // for round-robin
}

// InstanceState estado de una instancia específica
type InstanceState struct {
	URL        *url.URL
	Healthy    atomic.Bool
	LastCheck  atomic.Int64 // unix nano
	FailCount  atomic.Int32
}

// NewServiceRegistry crea el registry
func NewServiceRegistry(services []config.ServiceConfig, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *ServiceRegistry {
	r := &ServiceRegistry{
		services: make(map[string]*ServiceState),
		log:      log,
	}

	for _, svc := range services {
		state := &ServiceState{
			Config: svc,
		}
		for _, instance := range svc.Instances {
			u, err := url.Parse(instance)
			if err != nil {
				log.Error("Invalid instance URL", err, "service", svc.Name, "instance", instance)
				continue
			}
			inst := &InstanceState{URL: u}
			inst.Healthy.Store(true) // Asumir healthy al inicio
			inst.LastCheck.Store(time.Now().UnixNano())
			state.Instances = append(state.Instances, inst)
		}
		r.services[svc.Name] = state
	}

	return r
}

// GetService obtiene el estado de un servicio
func (r *ServiceRegistry) GetService(name string) (*ServiceState, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	s, ok := r.services[name]
	return s, ok
}

// GetNextInstance retorna la siguiente instancia healthy (round-robin)
func (s *ServiceState) GetNextInstance() *InstanceState {
	if len(s.Instances) == 0 {
		return nil
	}

	// Round-robin entre instancias healthy
	n := len(s.Instances)
	startIdx := s.CurrentCounter.Add(1) % uint64(n)

	for i := 0; i < n; i++ {
		idx := (int(startIdx) + i) % n
		inst := s.Instances[idx]
		if inst.Healthy.Load() {
			return inst
		}
	}

	// Si ninguna está healthy, retornar la primera (mejor que nada)
	return s.Instances[0]
}

// MarkUnhealthy marca una instancia como unhealthy
func (i *InstanceState) MarkUnhealthy() {
	count := i.FailCount.Add(1)
	if count >= 3 {
		i.Healthy.Store(false)
	}
}

// MarkHealthy marca una instancia como healthy
func (i *InstanceState) MarkHealthy() {
	i.Healthy.Store(true)
	i.FailCount.Store(0)
}

// StartHealthChecks inicia health checks periódicos
func (r *ServiceRegistry) StartHealthChecks(ctx context.Context, interval time.Duration) {
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				r.checkAll(ctx)
			}
		}
	}()
}

func (r *ServiceRegistry) checkAll(ctx context.Context) {
	client := &http.Client{Timeout: 3 * time.Second}

	r.mu.RLock()
	defer r.mu.RUnlock()

	for name, state := range r.services {
		for _, inst := range state.Instances {
			go func(name string, inst *InstanceState) {
				url := inst.URL.String() + state.Config.HealthPath
				req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
				resp, err := client.Do(req)
				if err != nil || resp.StatusCode >= 500 {
					inst.MarkUnhealthy()
					r.log.Warn("Instance unhealthy", "service", name, "instance", inst.URL.Host, "fails", inst.FailCount.Load())
				} else {
					inst.MarkHealthy()
				}
				inst.LastCheck.Store(time.Now().UnixNano())
			}(name, inst)
		}
	}
}

// AllHealthy retorna si todos los servicios requeridos están healthy
func (r *ServiceRegistry) AllHealthy() (bool, map[string]bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	allOk := true
	status := make(map[string]bool)

	for name, state := range r.services {
		anyHealthy := false
		for _, inst := range state.Instances {
			if inst.Healthy.Load() {
				anyHealthy = true
				break
			}
		}
		status[name] = anyHealthy
		if state.Config.Required && !anyHealthy {
			allOk = false
		}
	}

	return allOk, status
}

// ─── Reverse Proxy ─────────────────────────────────────────────

// ReverseProxy retorna un handler que hace proxy a un servicio
func ReverseProxy(
	registry *ServiceRegistry,
	serviceName string,
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
	natsConn *nats.Conn,
) gin.HandlerFunc {
	return func(c *gin.Context) {
		service, ok := registry.GetService(serviceName)
		if !ok {
			c.JSON(http.StatusNotFound, gin.H{"error": "service not found: " + serviceName})
			return
		}

		instance := service.GetNextInstance()
		if instance == nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"error":   "no healthy instances",
				"service": serviceName,
			})
			return
		}

		// Crear reverse proxy
		proxy := httputil.NewSingleHostReverseProxy(instance.URL)
		proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
			log.Error("Proxy error", err, "service", serviceName, "instance", instance.URL.Host)
			instance.MarkUnhealthy()
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			w.Write([]byte(`{"error":"upstream error","service":"` + serviceName + `"}`))
		}

		// Timeout del upstream
		timeout := time.Duration(service.Config.Timeout) * time.Millisecond
		if timeout == 0 {
			timeout = 30 * time.Second
		}
		ctx, cancel := context.WithTimeout(c.Request.Context(), timeout)
		defer cancel()

		c.Request = c.Request.WithContext(ctx)

		// Agregar headers para upstream
		c.Request.Header.Set("X-Forwarded-Host", c.Request.Host)
		c.Request.Header.Set("X-Real-IP", c.ClientIP())
		c.Request.Header.Set("X-Request-ID", c.GetString("request_id"))
		if tenantID, exists := c.Get("tenant_id"); exists {
			c.Request.Header.Set("X-Tenant-ID", tenantID.(string))
		}

		// Audit log a NATS (async, no bloqueante)
		if natsConn != nil {
			go publishProxyEvent(natsConn, serviceName, c, instance.URL.Host)
		}

		// Forward
		proxy.ServeHTTP(c.Writer, c.Request)
	}
}

func publishProxyEvent(nc *nats.Conn, service string, c *gin.Context, instance string) {
	subject := "gateway.request." + service
	payload := map[string]any{
		"request_id": c.GetString("request_id"),
		"service":    service,
		"instance":   instance,
		"method":     c.Request.Method,
		"path":       c.Request.URL.Path,
		"ip":         c.ClientIP(),
		"timestamp":  time.Now().Format(time.RFC3339Nano),
	}
	data, _ := jsonMarshal(payload)
	if err := nc.Publish(subject, data); err != nil {
		// Silent fail - métricas de NATS se manejan aparte
		_ = err
	}
}

// ─── Helpers ───────────────────────────────────────────────────

func jsonMarshal(v any) ([]byte, error) {
	return jsonMarshalImpl(v)
}

// Use direct encoding/json to keep things simple
// (avoiding extra abstraction)

// ─── Rate Limiter (per-user) ───────────────────────────────────

// UserRateLimiter rate limit por usuario (JWT-based)
type UserRateLimiter struct {
	rdb *redis.Client
}

// NewUserRateLimiter crea el limiter
func NewUserRateLimiter(rdb *redis.Client) *UserRateLimiter {
	return &UserRateLimiter{rdb: rdb}
}

// Allow verifica si el usuario puede hacer el request
func (u *UserRateLimiter) Allow(ctx context.Context, userID string, endpoint string, limit int) (bool, int, error) {
	key := "ratelimit:user:" + userID + ":" + endpoint
	pipe := u.rdb.Pipeline()
	incr := pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, time.Minute)
	if _, err := pipe.Exec(ctx); err != nil {
		return true, limit, err
	}
	count := int(incr.Val())
	return count <= limit, limit - count, nil
}