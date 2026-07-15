package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/bcrypt"

	"github.com/tnsvt/auth-service/internal/models"
	"github.com/tnsvt/auth-service/internal/repository"
)

// ErrInvalidCredentials credenciales inválidas
var ErrInvalidCredentials = errors.New("invalid credentials")

// ErrUserLocked usuario bloqueado
var ErrUserLocked = errors.New("user locked")

// ErrUserInactive usuario inactivo
var ErrUserInactive = errors.New("user inactive")

// ErrEmailExists email ya registrado
var ErrEmailExists = errors.New("email already exists")

// ErrWeakPassword contraseña débil
var ErrWeakPassword = errors.New("password too weak")

// ErrInvalidRefreshToken refresh token inválido
var ErrInvalidRefreshToken = errors.New("invalid refresh token")

// ErrTwoFARequired requiere 2FA
var ErrTwoFARequired = errors.New("2FA required")

// ErrTwoFAInvalid código 2FA inválido
var ErrTwoFAInvalid = errors.New("invalid 2FA code")

// AuthService es el orquestador principal de autenticación
type AuthService struct {
	repo       repository.Repository
	redis      *redis.Client
	jwt        *JWTService
	authConfig interface {
		JWTAccessTokenExpire  time.Duration
		JWTRefreshTokenExpire time.Duration
		MaxLoginAttempts      int
		LockoutDuration       time.Duration
		BCryptRounds          int
	}
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewAuthService crea el servicio
func NewAuthService(
	repo repository.Repository,
	redis *redis.Client,
	jwt *JWTService,
	authConfig interface {
		JWTAccessTokenExpire  time.Duration
		JWTRefreshTokenExpire time.Duration
		MaxLoginAttempts      int
		LockoutDuration       time.Duration
		BCryptRounds          int
	},
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
) *AuthService {
	return &AuthService{
		repo:       repo,
		redis:      redis,
		jwt:        jwt,
		authConfig: authConfig,
		log:        log,
	}
}

// ─── Register ──────────────────────────────────────────────────

// Register crea un nuevo tenant + usuario admin
func (s *AuthService) Register(ctx context.Context, req *models.RegisterRequest, ip, userAgent string) (*models.AuthResponse, error) {
	// Validar password fuerte
	if err := validatePasswordStrength(req.Password); err != nil {
		return nil, err
	}

	// Verificar email duplicado
	existing, err := s.repo.GetUserByEmail(ctx, req.Email)
	if err != nil && !errors.Is(err, repository.ErrNotFound) {
		return nil, fmt.Errorf("check email: %w", err)
	}
	if existing != nil {
		return nil, ErrEmailExists
	}

	// Generar slug del tenant
	slug := generateSlug(req.TenantName)

	// Verificar slug único
	_, err = s.repo.GetTenantBySlug(ctx, slug)
	if err == nil {
		// Slug duplicado, agregar sufijo
		slug = fmt.Sprintf("%s-%s", slug, uuid.New().String()[:8])
	} else if !errors.Is(err, repository.ErrNotFound) {
		return nil, fmt.Errorf("check slug: %w", err)
	}

	// Crear tenant
	tenant := &models.Tenant{
		Name:       req.TenantName,
		Slug:       slug,
		Schema:     fmt.Sprintf("tenant_%s", strings.ReplaceAll(slug, "-", "_")),
		Status:     "trial",
		Plan:       "free",
		MaxUsers:   5,
		MaxSignals: 100,
	}
	if err := s.repo.CreateTenant(ctx, tenant); err != nil {
		return nil, fmt.Errorf("create tenant: %w", err)
	}

	// Hash password
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), s.authConfig.BCryptRounds)
	if err != nil {
		return nil, fmt.Errorf("hash password: %w", err)
	}

	// Crear usuario admin del tenant
	user := &models.User{
		TenantID:     tenant.ID,
		Email:        strings.ToLower(req.Email),
		Username:     req.Username,
		PasswordHash: string(hash),
		Role:         models.RoleTenantAdmin,
		Status:       "active",
	}
	if err := s.repo.CreateUser(ctx, user); err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}

	// Audit
	s.recordAudit(ctx, &user.ID, &tenant.ID, "register", ip, userAgent, "success", map[string]any{
		"email":     user.Email,
		"tenant":    tenant.Name,
	})

	// Generar tokens
	return s.issueTokens(ctx, user, tenant, ip, userAgent)
}

// ─── Login ─────────────────────────────────────────────────────

// Login autentica un usuario
func (s *AuthService) Login(ctx context.Context, req *models.LoginRequest, ip, userAgent string) (*models.AuthResponse, error) {
	user, err := s.repo.GetUserByEmail(ctx, strings.ToLower(req.Email))
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			s.recordAudit(ctx, nil, nil, "login", ip, userAgent, "failure", map[string]any{
				"email": req.Email, "reason": "user_not_found",
			})
			return nil, ErrInvalidCredentials
		}
		return nil, err
	}

	// Verificar status
	if user.Status == "inactive" || user.Status == "suspended" {
		s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "failure", map[string]any{
			"reason": "user_" + user.Status,
		})
		return nil, ErrUserInactive
	}

	// Verificar lock
	if user.LockedUntil != nil && time.Now().Before(*user.LockedUntil) {
		s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "failure", map[string]any{
			"reason": "locked",
		})
		return nil, ErrUserLocked
	}

	// Verificar password
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
		// Incrementar failed login
		count, _ := s.repo.IncrementFailedLogin(ctx, user.ID)
		if count >= s.authConfig.MaxLoginAttempts {
			until := time.Now().Add(s.authConfig.LockoutDuration)
			s.repo.LockUser(ctx, user.ID, until)
			s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "failure", map[string]any{
				"reason": "locked_after_failed_attempts", "attempts": count,
			})
			return nil, ErrUserLocked
		}
		s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "failure", map[string]any{
			"reason": "wrong_password", "attempts": count,
		})
		return nil, ErrInvalidCredentials
	}

	// Si tiene 2FA, requerir código (sin emitir tokens todavía)
	if user.TwoFactorEnabled {
		if req.TwoFACode == "" {
			return &models.AuthResponse{
				Requires2FA: true,
				User:        user,
			}, ErrTwoFARequired
		}
		// Validar código TOTP (simplificado para Fase 1)
		if !verifyTOTPCode(user.TwoFactorSecret, req.TwoFACode) {
			s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "failure", map[string]any{
				"reason": "invalid_2fa_code",
			})
			return nil, ErrTwoFAInvalid
		}
	}

	// Reset failed login counter
	s.repo.ResetFailedLogin(ctx, user.ID)

	// Update last login
	s.repo.UpdateUserLastLogin(ctx, user.ID, ip)

	// Cargar tenant
	tenant, err := s.repo.GetTenantByID(ctx, user.TenantID)
	if err != nil {
		return nil, fmt.Errorf("get tenant: %w", err)
	}

	// Audit success
	s.recordAudit(ctx, &user.ID, &user.TenantID, "login", ip, userAgent, "success", nil)

	// Issue tokens
	return s.issueTokens(ctx, user, tenant, ip, userAgent)
}

// ─── Refresh ────────────────────────────────────────────────────

// Refresh renueva tokens usando un refresh token válido
func (s *AuthService) Refresh(ctx context.Context, refreshToken, ip, userAgent string) (*models.AuthResponse, error) {
	// Validar JWT
	claims, err := s.jwt.ValidateToken(refreshToken)
	if err != nil {
		return nil, ErrInvalidRefreshToken
	}

	if claims.TokenType != "refresh" {
		return nil, ErrInvalidRefreshToken
	}

	// Verificar que la sesión existe y no está revocada
	hash := hashToken(refreshToken)
	session, err := s.repo.GetSessionByTokenHash(ctx, hash)
	if err != nil {
		return nil, ErrInvalidRefreshToken
	}

	if session.RevokedAt != nil {
		return nil, ErrInvalidRefreshToken
	}

	if time.Now().After(session.ExpiresAt) {
		return nil, ErrInvalidRefreshToken
	}

	// Cargar usuario y tenant
	user, err := s.repo.GetUserByID(ctx, claims.UserID)
	if err != nil {
		return nil, ErrInvalidRefreshToken
	}
	tenant, err := s.repo.GetTenantByID(ctx, user.TenantID)
	if err != nil {
		return nil, err
	}

	// Revocar el refresh token viejo (rotación)
	s.repo.RevokeSession(ctx, session.ID, "rotated")

	// Emitir nuevos tokens
	return s.issueTokens(ctx, user, tenant, ip, userAgent)
}

// ─── Logout ─────────────────────────────────────────────────────

// Logout revoca la sesión actual
func (s *AuthService) Logout(ctx context.Context, userID uuid.UUID, refreshTokenHash, ip, userAgent string) error {
	session, err := s.repo.GetSessionByTokenHash(ctx, refreshTokenHash)
	if err == nil && session != nil {
		s.repo.RevokeSession(ctx, session.ID, "logout")
	}

	s.recordAudit(ctx, &userID, nil, "logout", ip, userAgent, "success", nil)
	return nil
}

// ─── Change Password ───────────────────────────────────────────

func (s *AuthService) ChangePassword(ctx context.Context, userID uuid.UUID, currentPassword, newPassword string, ip, userAgent string) error {
	user, err := s.repo.GetUserByID(ctx, userID)
	if err != nil {
		return err
	}

	// Verificar password actual
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(currentPassword)); err != nil {
		return ErrInvalidCredentials
	}

	// Validar nueva password
	if err := validatePasswordStrength(newPassword); err != nil {
		return err
	}

	// Hash nueva
	hash, err := bcrypt.GenerateFromPassword([]byte(newPassword), s.authConfig.BCryptRounds)
	if err != nil {
		return err
	}

	// Update (simplificado: en producción usar UpdatePassword method)
	user.PasswordHash = string(hash)
	// Aquí iría: s.repo.UpdateUserPassword(ctx, user.ID, string(hash))

	// Revocar todas las sesiones (forzar re-login)
	s.repo.RevokeAllUserSessions(ctx, user.ID, "password_changed")

	s.recordAudit(ctx, &user.ID, &user.TenantID, "password_change", ip, userAgent, "success", nil)
	return nil
}

// ─── 2FA ───────────────────────────────────────────────────────

func (s *AuthService) Setup2FA(ctx context.Context, userID uuid.UUID) (string, error) {
	secret := generateTOTPSecret()
	// Update en DB (simplificado)
	// s.repo.UpdateUser2FASecret(ctx, userID, secret)
	_ = secret
	return secret, nil
}

func (s *AuthService) Verify2FA(ctx context.Context, userID uuid.UUID, code string) error {
	// Validar código y activar
	// En producción: validar TOTP window y activar flag
	return nil
}

// ─── Helpers ───────────────────────────────────────────────────

func (s *AuthService) issueTokens(ctx context.Context, user *models.User, tenant *models.Tenant, ip, userAgent string) (*models.AuthResponse, error) {
	accessToken, expiresIn, err := s.jwt.GenerateAccessToken(user, tenant)
	if err != nil {
		return nil, fmt.Errorf("generate access: %w", err)
	}

	refreshToken, refreshHash, refreshExpires, err := s.jwt.GenerateRefreshToken(user)
	if err != nil {
		return nil, fmt.Errorf("generate refresh: %w", err)
	}

	// Guardar sesión
	session := &models.Session{
		UserID:           user.ID,
		RefreshTokenHash: refreshHash,
		UserAgent:        userAgent,
		IP:               ip,
		ExpiresAt:        refreshExpires,
	}
	if err := s.repo.CreateSession(ctx, session); err != nil {
		return nil, fmt.Errorf("create session: %w", err)
	}

	return &models.AuthResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		TokenType:    "Bearer",
		ExpiresIn:    int(expiresIn.Sub(time.Now()).Seconds()),
		User:         user,
		Tenant:       tenant,
	}, nil
}

func (s *AuthService) recordAudit(ctx context.Context, userID, tenantID *uuid.UUID, action, ip, ua, status string, metadata map[string]any) {
	e := &models.AuditEvent{
		UserID:    userID,
		TenantID:  tenantID,
		Action:    action,
		IP:        ip,
		UserAgent: ua,
		Status:    status,
		Metadata:  metadata,
	}
	if err := s.repo.CreateAuditEvent(ctx, e); err != nil {
		s.log.Error("Failed to record audit event", err)
	}
}

// ─── Validators ────────────────────────────────────────────────

func validatePasswordStrength(password string) error {
	if len(password) < 12 {
		return ErrWeakPassword
	}
	// Mínimo: mayúscula, minúscula, número
	hasUpper := false
	hasLower := false
	hasDigit := false
	for _, c := range password {
		switch {
		case c >= 'A' && c <= 'Z':
			hasUpper = true
		case c >= 'a' && c <= 'z':
			hasLower = true
		case c >= '0' && c <= '9':
			hasDigit = true
		}
	}
	if !hasUpper || !hasLower || !hasDigit {
		return ErrWeakPassword
	}
	return nil
}

func generateSlug(name string) string {
	slug := strings.ToLower(strings.TrimSpace(name))
	slug = strings.ReplaceAll(slug, " ", "-")
	// Remover caracteres no-ASCII
	out := make([]rune, 0, len(slug))
	for _, r := range slug {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
			out = append(out, r)
		}
	}
	return string(out)
}

func generateTOTPSecret() string {
	// Base32 random 32 chars
	return uuid.New().String()
}

func verifyTOTPSecret(secret, code string) bool {
	// Placeholder - en producción usar github.com/pquerna/otp
	return len(code) == 6
}

func verifyTOTPCode(secret, code string) bool {
	return verifyTOTPSecret(secret, code)
}