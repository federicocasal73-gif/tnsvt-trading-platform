package services

import (
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/tnsvt/auth-service/internal/models"
)

type jwtCfg struct {
	accessExpire  time.Duration
	refreshExpire time.Duration
	algo          string
}

func (c jwtCfg) JWTAccessTokenExpire() time.Duration  { return c.accessExpire }
func (c jwtCfg) JWTRefreshTokenExpire() time.Duration { return c.refreshExpire }
func (c jwtCfg) JWTAlgorithm() string                 { return c.algo }

type jwtCfgStruct struct {
	JWTAccessTokenExpireVal  time.Duration
	JWTRefreshTokenExpireVal time.Duration
	JWTAlgorithmVal          string
}

func (c jwtCfgStruct) JWTAccessTokenExpire() time.Duration  { return c.JWTAccessTokenExpireVal }
func (c jwtCfgStruct) JWTRefreshTokenExpire() time.Duration { return c.JWTRefreshTokenExpireVal }
func (c jwtCfgStruct) JWTAlgorithm() string                 { return c.JWTAlgorithmVal }

func newTestJWTSvc(t *testing.T, secret string) *JWTService {
	t.Helper()
	cfg := jwtCfgStruct{
		JWTAccessTokenExpireVal:  15 * time.Minute,
		JWTRefreshTokenExpireVal: 7 * 24 * time.Hour,
		JWTAlgorithmVal:          "test-algorithm-placeholder-string-here",
	}
	svc := NewJWTService(cfg, nil)
	svc.SetSecret(secret)
	return svc
}

func TestJWTGenerateAndValidateAccessToken(t *testing.T) {
	svc := newTestJWTSvc(t, "test-secret-must-be-at-least-32-chars")

	user := &models.User{
		ID:    uuid.New(),
		Email: "alice@example.com",
		Role:  "admin",
	}
	user.Username = "alice"
	tenant := &models.Tenant{ID: uuid.New(), Name: "Acme"}

	token, expiresAt, err := svc.GenerateAccessToken(user, tenant)
	if err != nil {
		t.Fatalf("GenerateAccessToken failed: %v", err)
	}
	if token == "" {
		t.Fatal("token is empty")
	}
	if expiresAt.IsZero() {
		t.Fatal("expiresAt is zero")
	}
	if time.Until(expiresAt) > 16*time.Minute {
		t.Errorf("expiresAt too far in future: %v", expiresAt)
	}

	claims, err := svc.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken failed: %v", err)
	}
	if claims.UserID != user.ID {
		t.Errorf("UserID = %s, want %s", claims.UserID, user.ID)
	}
	if claims.TenantID != tenant.ID {
		t.Errorf("TenantID = %s, want %s", claims.TenantID, tenant.ID)
	}
	if claims.Email != user.Email {
		t.Errorf("Email = %q, want %q", claims.Email, user.Email)
	}
	if claims.Role != "admin" {
		t.Errorf("Role = %q, want admin", claims.Role)
	}
	if claims.TokenType != "access" {
		t.Errorf("TokenType = %q, want access", claims.TokenType)
	}
}

func TestJWTGenerateRefreshToken(t *testing.T) {
	svc := newTestJWTSvc(t, "test-secret-must-be-at-least-32-chars")

	user := &models.User{ID: uuid.New(), Email: "bob@example.com", TenantID: uuid.New()}
	user.Username = "bob"

	token, hash, expiresAt, err := svc.GenerateRefreshToken(user)
	if err != nil {
		t.Fatalf("GenerateRefreshToken failed: %v", err)
	}
	if token == "" {
		t.Fatal("token is empty")
	}
	if hash == "" {
		t.Fatal("hash is empty")
	}
	if hash == token {
		t.Error("hash equals token (should be different)")
	}
	if expiresAt.IsZero() {
		t.Fatal("expiresAt is zero")
	}

	claims, err := svc.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken failed: %v", err)
	}
	if claims.TokenType != "refresh" {
		t.Errorf("TokenType = %q, want refresh", claims.TokenType)
	}
}

func TestJWTValidateExpiredToken(t *testing.T) {
	cfg := jwtCfgStruct{
		JWTAccessTokenExpireVal:  -1 * time.Hour,
		JWTRefreshTokenExpireVal: time.Hour,
		JWTAlgorithmVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)
	svc.SetSecret("test-secret-must-be-at-least-32-chars")

	user := &models.User{ID: uuid.New(), Email: "x@y.com", TenantID: uuid.New()}
	user.Username = "x"
	tenant := &models.Tenant{ID: uuid.New(), Name: "T"}

	token, _, err := svc.GenerateAccessToken(user, tenant)
	if err != nil {
		t.Fatalf("GenerateAccessToken failed: %v", err)
	}

	_, err = svc.ValidateToken(token)
	if err != ErrExpiredToken {
		t.Errorf("ValidateToken = %v, want ErrExpiredToken", err)
	}
}

func TestJWTValidateInvalidSignature(t *testing.T) {
	svcA := newTestJWTSvc(t, "secret-A-must-be-at-least-32-chars-long")
	svcB := newTestJWTSvc(t, "secret-B-must-be-at-least-32-chars-long")

	user := &models.User{ID: uuid.New(), Email: "x@y.com", TenantID: uuid.New()}
	user.Username = "x"
	tenant := &models.Tenant{ID: uuid.New(), Name: "T"}

	token, _, err := svcA.GenerateAccessToken(user, tenant)
	if err != nil {
		t.Fatalf("GenerateAccessToken failed: %v", err)
	}

	_, err = svcB.ValidateToken(token)
	if err != ErrInvalidToken {
		t.Errorf("ValidateToken cross-secret = %v, want ErrInvalidToken", err)
	}
}

func TestJWTValidateMalformed(t *testing.T) {
	svc := newTestJWTSvc(t, "test-secret-must-be-at-least-32-chars")

	tests := []string{"", "not-a-token", "a.b.c", "only.two"}
	for _, tok := range tests {
		t.Run(tok, func(t *testing.T) {
			_, err := svc.ValidateToken(tok)
			if err != ErrInvalidToken {
				t.Errorf("ValidateToken(%q) = %v, want ErrInvalidToken", tok, err)
			}
		})
	}
}

func TestJWTSetSecretRejectsShort(t *testing.T) {
	cfg := jwtCfgStruct{
		JWTAccessTokenExpireVal:  time.Hour,
		JWTRefreshTokenExpireVal: time.Hour,
		JWTAlgorithmVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)

	originalSecret := svc.secret
	svc.SetSecret("too-short")
	if string(svc.secret) != string(originalSecret) {
		t.Error("SetSecret accepted short secret (should keep original)")
	}
}