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

func (c jwtCfg) JWTAccessTokenExpireVal() time.Duration  { return c.accessExpire }
func (c jwtCfg) JWTRefreshTokenExpireVal() time.Duration { return c.refreshExpire }
func (c jwtCfg) JWTAlgorithmVal() string                 { return c.algo }
func (c jwtCfg) GetJWTSecret() string                    { return "test-secret-must-be-at-least-32-chars" }

type jwtCfgStruct struct {
	accessExpireVal  time.Duration
	refreshExpireVal time.Duration
	algoVal          string
}

func (c jwtCfgStruct) JWTAccessTokenExpireVal() time.Duration  { return c.accessExpireVal }
func (c jwtCfgStruct) JWTRefreshTokenExpireVal() time.Duration { return c.refreshExpireVal }
func (c jwtCfgStruct) JWTAlgorithmVal() string                 { return c.algoVal }
func (c jwtCfgStruct) GetJWTSecret() string                    { return "test-secret-must-be-at-least-32-chars" }

func newTestJWTSvc(t *testing.T, secret string) *JWTService {
	t.Helper()
	cfg := jwtCfgStruct{
		accessExpireVal:  15 * time.Minute,
		refreshExpireVal: 7 * 24 * time.Hour,
		algoVal:          "test-algorithm-placeholder-string-here",
	}
	svc := NewJWTService(cfg, nil)
	if err := svc.SetSecret(secret); err != nil {
		t.Fatalf("SetSecret: %v", err)
	}
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
		accessExpireVal:  -1 * time.Hour,
		refreshExpireVal: time.Hour,
		algoVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)
	if err := svc.SetSecret("test-secret-must-be-at-least-32-chars"); err != nil {
		t.Fatalf("SetSecret: %v", err)
	}

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
		accessExpireVal:  time.Hour,
		refreshExpireVal: time.Hour,
		algoVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)

	originalSecret := svc.secret
	// A2 fix: SetSecret ahora retorna error en lugar de silent-fail.
	err := svc.SetSecret("too-short")
	if err == nil {
		t.Error("SetSecret debería retornar error para secret < 32 chars")
	}
	if string(svc.secret) != string(originalSecret) {
		t.Error("SetSecret accepted short secret (should keep original)")
	}
}

func TestJWTSetSecretRejectsPlaceholder(t *testing.T) {
	cfg := jwtCfgStruct{
		accessExpireVal:  time.Hour,
		refreshExpireVal: time.Hour,
		algoVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)

	// A1 fix: el placeholder público debe ser rechazado.
	err := svc.SetSecret(PlaceholderSecret)
	if err == nil {
		t.Error("SetSecret debería rechazar el placeholder de dev")
	}
}

func TestIsConfigured(t *testing.T) {
	cfg := jwtCfgStruct{
		accessExpireVal:  time.Hour,
		refreshExpireVal: time.Hour,
		algoVal:          "placeholder",
	}
	svc := NewJWTService(cfg, nil)

	// Después de NewJWTService con el secret default del .env (32+ chars),
	// el service está configurado (porque NewJWTService no es fatal — solo
	// loguea error y devuelve secret vacío si falla validateSecret).
	// El test aquí verifica que IsConfigured refleja el estado real.
	// Si el env tiene secret válido, IsConfigured=true.
	if svc.secret != nil && len(svc.secret) >= MinJWTSecretLength && string(svc.secret) != PlaceholderSecret {
		if !svc.IsConfigured() {
			t.Error("IsConfigured debería ser true con secret válido")
		}
	}
}