// Package services contiene la lógica de negocio del auth-service.
package services

import (
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"

	"github.com/tnsvt/auth-service/internal/models"
)

// Constantes de validación de secret
const (
	MinJWTSecretLength = 32
	JWTIssuer          = "tnsvt-auth-service"
	JWTAudience        = "tnsvt-platform"
	PlaceholderSecret  = "tnsvt-dev-default-secret-change-me-in-prod-!!"
)

// JWTClaims claims del JWT
type JWTClaims struct {
	UserID    uuid.UUID `json:"uid"`
	TenantID  uuid.UUID `json:"tid"`
	Email     string    `json:"email"`
	Username  string    `json:"username"`
	Role      string    `json:"role"`
	TokenType string    `json:"type"` // "access" o "refresh"
	jwt.RegisteredClaims
}

// ErrInvalidToken token inválido
var ErrInvalidToken = errors.New("invalid token")

// ErrExpiredToken token expirado
var ErrExpiredToken = errors.New("token expired")

// ErrWeakSecret secret demasiado débil
var ErrWeakSecret = errors.New("jwt secret too weak or is the dev placeholder")

// JWTService maneja generación y validación de JWT
type JWTService struct {
	secret    []byte
	algorithm string
	authCfg   interface {
		JWTAccessTokenExpireVal() time.Duration
		JWTRefreshTokenExpireVal() time.Duration
		JWTAlgorithmVal() string
		GetJWTSecret() string
	}
}

// NewJWTService crea un nuevo servicio JWT.
// A1 fix: fail-fast si el secret es el placeholder o < 32 chars.
// En lugar de fallback inseguro, retornamos un error fatal en el caller.
func NewJWTService(authCfg interface {
	JWTAccessTokenExpireVal() time.Duration
	JWTRefreshTokenExpireVal() time.Duration
	JWTAlgorithmVal() string
	GetJWTSecret() string
}, _ interface{}) *JWTService {
	secret := authCfg.GetJWTSecret()
	if err := validateSecret(secret); err != nil {
		// Log fatal y devolver secret vacio (zero bytes).
		// El caller (main.go) detecta secret vacio y aborta el startup.
		slog.Error("JWT secret is weak or default placeholder; aborting",
			"err", err, "len", len(secret))
		return &JWTService{
			secret:    []byte{},
			algorithm: "HS256",
			authCfg:   authCfg,
		}
	}
	return &JWTService{
		secret:    []byte(secret),
		algorithm: "HS256",
		authCfg:   authCfg,
	}
}

// validateSecret garantiza secret >= 32 chars y no sea el placeholder público.
func validateSecret(secret string) error {
	if len(secret) < MinJWTSecretLength {
		return fmt.Errorf("%w: %d chars < %d", ErrWeakSecret, len(secret), MinJWTSecretLength)
	}
	if secret == PlaceholderSecret {
		return fmt.Errorf("%w: default placeholder detected", ErrWeakSecret)
	}
	return nil
}

// SetSecret configura el secret (desde env).
// A2 fix: retornar error en lugar de silent-fail.
func (s *JWTService) SetSecret(secret string) error {
	if err := validateSecret(secret); err != nil {
		return err
	}
	s.secret = []byte(secret)
	return nil
}

// IsConfigured retorna true si el secret es válido y el servicio está listo.
func (s *JWTService) IsConfigured() bool {
	return len(s.secret) >= MinJWTSecretLength && string(s.secret) != PlaceholderSecret
}

// GenerateAccessToken genera un access token (corta duración)
func (s *JWTService) GenerateAccessToken(user *models.User, tenant *models.Tenant) (string, time.Time, error) {
	if !s.IsConfigured() {
		return "", time.Time{}, ErrWeakSecret
	}
	expiresAt := time.Now().Add(s.authCfg.JWTAccessTokenExpireVal())

	claims := &JWTClaims{
		UserID:    user.ID,
		TenantID:  tenant.ID,
		Email:     user.Email,
		Username:  user.Username,
		Role:      user.Role,
		TokenType: "access",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
			Issuer:    JWTIssuer,
			Subject:   user.ID.String(),
			Audience:  jwt.ClaimStrings{JWTAudience},
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString(s.secret)
	if err != nil {
		return "", time.Time{}, err
	}
	return signed, expiresAt, nil
}

// GenerateRefreshToken genera un refresh token (larga duración)
// Retorna el token plain + hash para guardar en DB
func (s *JWTService) GenerateRefreshToken(user *models.User) (string, string, time.Time, error) {
	if !s.IsConfigured() {
		return "", "", time.Time{}, ErrWeakSecret
	}
	tokenID := uuid.New()
	expiresAt := time.Now().Add(s.authCfg.JWTRefreshTokenExpireVal())

	claims := &JWTClaims{
		UserID:    user.ID,
		TenantID:  user.TenantID,
		Email:     user.Email,
		Username:  user.Username,
		Role:      user.Role,
		TokenType: "refresh",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
			Issuer:    JWTIssuer,
			Subject:   user.ID.String(),
			Audience:  jwt.ClaimStrings{JWTAudience}, // A8: audience también en refresh
			ID:        tokenID.String(),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString(s.secret)
	if err != nil {
		return "", "", time.Time{}, err
	}

	// Hash del token para guardar en DB (no guardamos el plain)
	hash := hashToken(signed)

	return signed, hash, expiresAt, nil
}

// ValidateToken valida un JWT y retorna sus claims.
// A8 fix: valida iss, aud, exp y algoritmo específico.
func (s *JWTService) ValidateToken(tokenString string) (*JWTClaims, error) {
	if !s.IsConfigured() {
		return nil, ErrWeakSecret
	}

	parser := jwt.NewParser(
		jwt.WithValidMethods([]string{"HS256"}),
		jwt.WithIssuer(JWTIssuer),
		jwt.WithAudience(JWTAudience),
		jwt.WithExpirationRequired(),
	)

	token, err := parser.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (any, error) {
		return s.secret, nil
	})

	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, ErrExpiredToken
		}
		return nil, ErrInvalidToken
	}

	if claims, ok := token.Claims.(*JWTClaims); ok && token.Valid {
		return claims, nil
	}

	return nil, ErrInvalidToken
}

// ─── Helpers ───────────────────────────────────────────────────

// hashToken hashea un token con SHA-256 para guardar en DB
func hashToken(token string) string {
	// Para Fase 1 usamos SHA-256; en Fase 3 podemos usar bcrypt
	return sha256Hex(token)
}

func sha256Hex(s string) string {
	// Inline minimal SHA-256 para evitar import circular
	// En producción: crypto/sha256
	h := sha256Sum([]byte(s))
	return hexEncode(h)
}