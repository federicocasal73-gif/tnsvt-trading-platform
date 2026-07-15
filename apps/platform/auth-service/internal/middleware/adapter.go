// Adapter para que JWTService del paquete services implemente JWTValidator del middleware.
package middleware

import (
	"github.com/tnsvt/auth-service/internal/services"
)

// Make sure the JWT service implements the JWTValidator interface
var _ JWTValidator = (*JWTServiceAdapter)(nil)

// JWTServiceAdapter adapts services.JWTService to middleware.JWTValidator
type JWTServiceAdapter struct {
	Service *services.JWTService
}

// ValidateToken implements JWTValidator
func (a *JWTServiceAdapter) ValidateToken(tokenString string) (*JWTClaimsLite, error) {
	claims, err := a.Service.ValidateToken(tokenString)
	if err != nil {
		return nil, err
	}
	return &JWTClaimsLite{
		UserID:   claims.UserID,
		TenantID: claims.TenantID,
		Email:    claims.Email,
		Role:     claims.Role,
	}, nil
}