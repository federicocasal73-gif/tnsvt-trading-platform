// Package services contiene la lógica de negocio del auth-service.
package services

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"

	"github.com/tnsvt/auth-service/internal/models"
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

// NewJWTService crea un nuevo servicio JWT
func NewJWTService(authCfg interface {
	JWTAccessTokenExpireVal() time.Duration
	JWTRefreshTokenExpireVal() time.Duration
	JWTAlgorithmVal() string
	GetJWTSecret() string
}, _ interface{}) *JWTService {
	secret := authCfg.GetJWTSecret()
	if len(secret) < 32 {
		secret = "tnsvt-dev-default-secret-change-me-in-prod-!!"
	}
	return &JWTService{
		secret:    []byte(secret),
		algorithm: "HS256",
		authCfg:   authCfg,
	}
}

// SetSecret configura el secret (desde env)
func (s *JWTService) SetSecret(secret string) {
	if len(secret) >= 32 {
		s.secret = []byte(secret)
	}
}

// GenerateAccessToken genera un access token (corta duración)
func (s *JWTService) GenerateAccessToken(user *models.User, tenant *models.Tenant) (string, time.Time, error) {
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
			Issuer:    "tnsvt-auth-service",
			Subject:   user.ID.String(),
			Audience:  jwt.ClaimStrings{"tnsvt-platform"},
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
			Issuer:    "tnsvt-auth-service",
			Subject:   user.ID.String(),
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

// ValidateToken valida un JWT y retorna sus claims
func (s *JWTService) ValidateToken(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (any, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, ErrInvalidToken
		}
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