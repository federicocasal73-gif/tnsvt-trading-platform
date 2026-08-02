package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
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
		JWTAccessTokenExpireVal() time.Duration
		JWTRefreshTokenExpireVal() time.Duration
		MaxLoginAttemptsVal() int
		LockoutDurationVal() time.Duration
		BCryptRoundsVal() int
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
		JWTAccessTokenExpireVal() time.Duration
		JWTRefreshTokenExpireVal() time.Duration
		MaxLoginAttemptsVal() int
		LockoutDurationVal() time.Duration
		BCryptRoundsVal() int
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
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), s.authConfig.BCryptRoundsVal())
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
		s.log.Error("GetUserByEmail failed", err, "email", req.Email)
		return nil, fmt.Errorf("get user: %w", err)
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
		// A5: IncrementAndMaybeLock atómico (1 query) en lugar de
		// IncrementFailedLogin + LockUser (2 queries, race condition).
		count, locked, ilErr := s.repo.IncrementAndMaybeLock(
			ctx, user.ID,
			s.authConfig.MaxLoginAttemptsVal(),
			s.authConfig.LockoutDurationVal(),
		)
		if ilErr != nil {
			s.log.Error("IncrementAndMaybeLock failed", ilErr, "user_id", user.ID)
		}
		if locked {
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
		s.log.Error("GetTenantByID failed", err, "user_id", user.ID, "tenant_id", user.TenantID)
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
	s.log.Info("ChangePassword called", "user_id", userID.String())
	user, err := s.repo.GetUserByID(ctx, userID)
	if err != nil {
		s.log.Error("GetUserByID failed", err, "user_id_str", userID.String(), "user_id_bytes", fmt.Sprintf("%x", userID[:]))
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
	hash, err := bcrypt.GenerateFromPassword([]byte(newPassword), s.authConfig.BCryptRoundsVal())
	if err != nil {
		return err
	}

	// Persistir el nuevo hash. Reset failed_login_count y locked_until.
	if err := s.repo.UpdateUserPassword(ctx, user.ID, string(hash)); err != nil {
		s.log.Error("UpdateUserPassword failed", err, "user_id", user.ID)
		return fmt.Errorf("update password: %w", err)
	}
	user.PasswordHash = string(hash)

	// Revocar todas las sesiones (forzar re-login)
	s.repo.RevokeAllUserSessions(ctx, user.ID, "password_changed")

	s.recordAudit(ctx, &user.ID, &user.TenantID, "password_change", ip, userAgent, "success", nil)
	return nil
}

// ─── 2FA ───────────────────────────────────────────────────────

// A4 fix: Setup2FA persiste el secret con two_factor_enabled=FALSE.
// El flag solo se activa tras Verify2FA exitoso.
func (s *AuthService) Setup2FA(ctx context.Context, userID uuid.UUID) (string, error) {
	secret, err := generateTOTPSecret()
	if err != nil {
		s.log.Error("generateTOTPSecret failed", err, "user_id", userID)
		return "", fmt.Errorf("generate totp secret: %w", err)
	}
	// Setup usa el nuevo método que NO auto-activa.
	if err := s.repo.Setup2FASecret(ctx, userID, secret); err != nil {
		s.log.Error("Setup2FASecret failed", err, "user_id", userID)
		return "", fmt.Errorf("persist 2fa secret: %w", err)
	}
	return secret, nil
}

// Verify2FA valida el código TOTP. Si es correcto, ACTIVA two_factor_enabled
// (paso 2 del setup). Si ya estaba enabled, solo valida.
func (s *AuthService) Verify2FA(ctx context.Context, userID uuid.UUID, code string) error {
	user, err := s.repo.GetUserByID(ctx, userID)
	if err != nil {
		return fmt.Errorf("user lookup: %w", err)
	}
	if user.TwoFactorSecret == "" {
		return errors.New("2FA not configured — call Setup2FA first")
	}
	ok, verifyErr := verifyTOTPSecret(user.TwoFactorSecret, code)
	if !ok {
		if verifyErr != nil {
			s.log.Warn("2FA verify failed", "err", verifyErr, "user_id", userID)
		}
		return errors.New("invalid 2fa code")
	}
	// A4: Si NO estaba activado, activarlo ahora (paso 2 del setup).
	if !user.TwoFactorEnabled {
		if err := s.repo.Enable2FA(ctx, userID); err != nil {
			s.log.Error("Enable2FA failed after successful verify", err, "user_id", userID)
			return fmt.Errorf("enable 2fa: %w", err)
		}
		s.log.Info("2FA enabled after successful verify", "user_id", userID)
	}
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

// otpDigitsSix y otpAlgorithmSHA1 son aliases para las constantes
// no-exportadas de github.com/pquerna/otp. Definidas aquí para
// evitar import circular con jwt.go y mantener el código legible.
// Los tipos son `int` según otp.go (Digits int, Algorithm int).
const (
	otpDigitsSix    int = 6  // totp.DigitsSix equivalente (DigitsSix Digits = 6)
	otpAlgorithmSHA1 int = 0  // totp.AlgorithmSHA1 equivalente (AlgorithmSHA1 Algorithm = iota 0)
)

// validatePasswordStrength enforces política de password.
// A6 fix: strengthened con símbolo + chequeo de entropía simple.
// TODO Fase 3: integrar zxcvbn-go para detectar common passwords.
func validatePasswordStrength(password string) error {
	if len(password) < 12 {
		return ErrWeakPassword
	}
	if len(password) > 128 {
		return ErrWeakPassword // evitar DoS con passwords muy largos
	}
	hasUpper := false
	hasLower := false
	hasDigit := false
	hasSymbol := false
	for _, c := range password {
		switch {
		case c >= 'A' && c <= 'Z':
			hasUpper = true
		case c >= 'a' && c <= 'z':
			hasLower = true
		case c >= '0' && c <= '9':
			hasDigit = true
		case (c >= '!' && c <= '/') || (c >= ':' && c <= '@') ||
			(c >= '[' && c <= '`') || (c >= '{' && c <= '~'):
			hasSymbol = true
		}
	}
	if !hasUpper || !hasLower || !hasDigit || !hasSymbol {
		return ErrWeakPassword
	}
	// Chequeo básico de entropía: no permitir repeticiones obvias.
	// (zxcvbn real vendría en una iteración posterior.)
	if hasAllSameChar(password) {
		return ErrWeakPassword
	}
	return nil
}

// hasAllSameChar detecta passwords triviales como "aaaaaaaaaaaa".
func hasAllSameChar(s string) bool {
	if len(s) < 4 {
		return false
	}
	first := s[0]
	for i := 1; i < len(s); i++ {
		if s[i] != first {
			return false
		}
	}
	return true
}

func generateSlug(name string) string {
	slug := strings.ToLower(strings.TrimSpace(name))
	// Colapsar runs de espacios en un solo guión
	slug = strings.Join(strings.Fields(slug), "-")
	// Remover caracteres no-ASCII / no alfanuméricos (excepto '-')
	out := make([]rune, 0, len(slug))
	prevDash := false
	for _, r := range slug {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			out = append(out, r)
			prevDash = false
		} else if r == '-' && !prevDash && len(out) > 0 {
			out = append(out, r)
			prevDash = true
		}
	}
	// Trim trailing dash
	if len(out) > 0 && out[len(out)-1] == '-' {
		out = out[:len(out)-1]
	}
	return string(out)
}

// A3 fix: TOTP real con github.com/pquerna/otp (RFC 6238).
// Setup2FA ya NO activa el flag enabled=true (A4). Solo se activa
// tras verifyTOTPCode exitoso (ver Setup2FA / Verify2FA en handlers).

// generateTOTPSecret genera un secret Base32 de 32 chars (estándar TOTP).
func generateTOTPSecret() (string, error) {
	key, err := totp.Generate(totp.GenerateOpts{
		Issuer:      JWTIssuer,
		AccountName: "tnsvt-user",
		Period:      30,
		Digits:      otp.Digits(otpDigitsSix),
		Algorithm:   otp.Algorithm(otpAlgorithmSHA1),
	})
	if err != nil {
		return "", fmt.Errorf("generate TOTP secret: %w", err)
	}
	return key.Secret(), nil
}

// verifyTOTPSecret valida el código TOTP contra el secret.
// Ventana: ±1 step (30s antes/después, default de la librería).
func verifyTOTPSecret(secret, code string) (bool, error) {
	if len(code) != 6 {
		return false, nil
	}
	if secret == "" {
		return false, errors.New("totp secret not configured for user")
	}
	pass, err := totp.ValidateCustom(code, secret, time.Now(), totp.ValidateOpts{
		Period:    30,
		Skew:      1,
		Digits:    otp.Digits(otpDigitsSix),
		Algorithm: otp.Algorithm(otpAlgorithmSHA1),
	})
	if err != nil {
		return false, nil
	}
	return pass, nil
}

// verifyTOTPCode wrap que descarta el error (compatibilidad).
func verifyTOTPCode(secret, code string) bool {
	ok, _ := verifyTOTPSecret(secret, code)
	return ok
}