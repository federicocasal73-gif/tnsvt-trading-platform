// Package circuit implements a circuit breaker pattern for Go services.
// Portado de signal_copier/circuit_breaker.py (Python) a Go.
//
// Uso:
//
//	cb := circuit.New(circuit.Config{
//	    Name:             "tnsvt-client",
//	    FailureThreshold: 5,
//	    RecoveryTimeout:  30 * time.Second,
//	})
//
//	err := cb.Execute(func() error {
//	    return client.DoRequest()
//	})
package circuit

import (
	"errors"
	"sync"
	"time"
)

// State representa el estado del circuit breaker
type State int

const (
	StateClosed   State = iota // Funcionando normal
	StateOpen                  // Fallando, rechaza requests
	StateHalfOpen              // Probando si el sistema se recuperó
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half_open"
	}
	return "unknown"
}

// ErrCircuitOpen se retorna cuando el circuit breaker está abierto
var ErrCircuitOpen = errors.New("circuit breaker is open")

// Config configuración del circuit breaker
type Config struct {
	Name             string
	FailureThreshold int           // Número de fallos para abrir
	SuccessThreshold int           // Éxitos en half-open para cerrar
	RecoveryTimeout  time.Duration // Tiempo en open antes de half-open
	OnStateChange    func(name string, from, to State)
}

// Breaker circuit breaker
type Breaker struct {
	mu               sync.RWMutex
	config           Config
	state            State
	failures         int
	successes        int
	lastFailure      time.Time
	halfOpenInflight bool
}

// New crea un nuevo circuit breaker
func New(config Config) *Breaker {
	if config.FailureThreshold <= 0 {
		config.FailureThreshold = 5
	}
	if config.SuccessThreshold <= 0 {
		config.SuccessThreshold = 2
	}
	if config.RecoveryTimeout <= 0 {
		config.RecoveryTimeout = 30 * time.Second
	}
	return &Breaker{
		config: config,
		state:  StateClosed,
	}
}

// Execute ejecuta una función bajo la protección del circuit breaker
func (b *Breaker) Execute(fn func() error) error {
	if !b.allow() {
		return ErrCircuitOpen
	}

	err := fn()
	b.record(err)
	return err
}

// State retorna el estado actual
func (b *Breaker) State() State {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return b.state
}

// Stats retorna estadísticas del breaker
func (b *Breaker) Stats() map[string]any {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return map[string]any{
		"name":     b.config.Name,
		"state":    b.state.String(),
		"failures": b.failures,
		"success":  b.successes,
	}
}

// allow verifica si se puede ejecutar la función
func (b *Breaker) allow() bool {
	b.mu.Lock()
	defer b.mu.Unlock()

	switch b.state {
	case StateClosed:
		return true
	case StateOpen:
		if time.Since(b.lastFailure) > b.config.RecoveryTimeout {
			b.transition(StateHalfOpen)
			b.halfOpenInflight = true
			return true
		}
		return false
	case StateHalfOpen:
		if b.halfOpenInflight {
			return false
		}
		b.halfOpenInflight = true
		return true
	}
	return false
}

// record registra el resultado de una ejecución
func (b *Breaker) record(err error) {
	b.mu.Lock()
	defer b.mu.Unlock()

	if err == nil {
		b.onSuccess()
	} else {
		b.onFailure()
	}

	if b.state == StateHalfOpen {
		b.halfOpenInflight = false
	}
}

// onSuccess se llama cuando una ejecución es exitosa
func (b *Breaker) onSuccess() {
	b.successes++
	switch b.state {
	case StateHalfOpen:
		if b.successes >= b.config.SuccessThreshold {
			b.transition(StateClosed)
			b.failures = 0
			b.successes = 0
		}
	case StateClosed:
		b.failures = 0
	}
}

// onFailure se llama cuando una ejecución falla
func (b *Breaker) onFailure() {
	b.failures++
	b.lastFailure = time.Now()
	switch b.state {
	case StateClosed:
		if b.failures >= b.config.FailureThreshold {
			b.transition(StateOpen)
		}
	case StateHalfOpen:
		b.transition(StateOpen)
	case StateOpen:
		// Ya está abierto
	}
}

// transition cambia de estado
func (b *Breaker) transition(to State) {
	from := b.state
	b.state = to
	if b.config.OnStateChange != nil {
		go b.config.OnStateChange(b.config.Name, from, to)
	}
}

// Registry mantiene un registro global de breakers
type Registry struct {
	mu       sync.RWMutex
	breakers map[string]*Breaker
}

// NewRegistry crea un nuevo registry
func NewRegistry() *Registry {
	return &Registry{
		breakers: make(map[string]*Breaker),
	}
}

// Get obtiene o crea un breaker
func (r *Registry) Get(name string, config Config) *Breaker {
	r.mu.RLock()
	if b, ok := r.breakers[name]; ok {
		r.mu.RUnlock()
		return b
	}
	r.mu.RUnlock()

	r.mu.Lock()
	defer r.mu.Unlock()

	if b, ok := r.breakers[name]; ok {
		return b
	}

	if config.Name == "" {
		config.Name = name
	}
	b := New(config)
	r.breakers[name] = b
	return b
}

// All retorna todos los breakers
func (r *Registry) All() map[string]*Breaker {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make(map[string]*Breaker, len(r.breakers))
	for k, v := range r.breakers {
		out[k] = v
	}
	return out
}