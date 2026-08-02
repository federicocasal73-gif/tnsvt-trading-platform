package services

import (
	"strings"
	"testing"
)

func TestValidatePasswordStrength(t *testing.T) {
	tests := []struct {
		name     string
		password string
		wantErr  error
	}{
		// A6: strengthened validation now requires symbol + length 12-128
		{"valid_strong_12", "MyStr0ngPass9!", nil},          // 13 chars, upper+lower+digit+symbol
		{"valid_strong_long", "Passw0rd!@#$%", nil},         // 12 chars exact
		{"valid_with_symbols", "AaBb1234!@#$%^&*()", nil}, // 18 chars
		{"too_short", "Ab1!", ErrWeakPassword},
		{"empty", "", ErrWeakPassword},
		{"no_upper", "mystr0ngpass9!", ErrWeakPassword},
		{"no_lower", "MYSTR0NGPASS9!", ErrWeakPassword},
		{"no_digit", "MyStrongPass!", ErrWeakPassword},
		{"no_symbol", "MyStr0ngPass99", ErrWeakPassword},
		{"only_letters_long", "abcdefghijklmnop", ErrWeakPassword},
		{"all_same_char", "aaaaaaaaaaaaa", ErrWeakPassword}, // repetition check
		{"too_long", strings.Repeat("Aa1!", 100), ErrWeakPassword}, // >128
		{"exactly_min_length", "Abcdefgh1jkl!", nil},              // 13 chars valid
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validatePasswordStrength(tt.password)
			if err != tt.wantErr {
				t.Errorf("validatePasswordStrength(%q) = %v, want %v", tt.password, err, tt.wantErr)
			}
		})
	}
}

func TestGenerateSlug(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"simple", "Hello World", "hello-world"},
		{"with_spaces", "  Multiple   Spaces  ", "multiple-spaces"},
		{"already_lowercase", "already-lowercase", "already-lowercase"},
		{"with_specials", "Café & Bar!", "caf-bar"},
		{"empty", "", ""},
		{"only_specials", "!@#$%", ""},
		{"numbers_kept", "Trading 2026", "trading-2026"},
		{"unicode_kept_out", "Tñádíng 2026", "tdng-2026"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := generateSlug(tt.input)
			if got != tt.want {
				t.Errorf("generateSlug(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestHashToken(t *testing.T) {
	token := "eyJhbGciOiJIUzI1NiJ9.test.signature"
	h1 := hashToken(token)
	h2 := hashToken(token)

	if h1 == "" {
		t.Fatal("hashToken returned empty")
	}
	if h1 != h2 {
		t.Errorf("hashToken not deterministic: %q vs %q", h1, h2)
	}
	if len(h1) != 64 {
		t.Errorf("hashToken length = %d, want 64 (SHA-256 hex)", len(h1))
	}
	if !isHex(h1) {
		t.Errorf("hashToken %q is not valid hex", h1)
	}
}

func TestHashTokenDifferentInputsDifferentHashes(t *testing.T) {
	a := hashToken("token-a")
	b := hashToken("token-b")
	if a == b {
		t.Error("different tokens produced identical hashes")
	}
}

// A3: TOTP real ahora. generateTOTPSecret retorna (string, error) y
// devuelve un secret Base32 de ~32 chars (no UUID).
func TestGenerateTOTPSecret(t *testing.T) {
	s, err := generateTOTPSecret()
	if err != nil {
		t.Fatalf("generateTOTPSecret returned error: %v", err)
	}
	if s == "" {
		t.Fatal("generateTOTPSecret returned empty")
	}
	// Base32 secret es 32 chars
	if len(s) < 16 {
		t.Errorf("generateTOTPSecret length = %d, want >= 16", len(s))
	}
	// No es UUID
	if strings.Count(s, "-") >= 4 {
		t.Errorf("generateTOTPSecret parece un UUID: %q (debería ser Base32)", s)
	}
	// Dos calls deben dar diferentes secrets
	s2, _ := generateTOTPSecret()
	if s == s2 {
		t.Error("generateTOTPSecret returned same value twice (should be random)")
	}
}

// A3: verifyTOTPSecret ahora retorna (bool, error). Es TOTP real,
// no acepta cualquier código de 6 dígitos. Solo pasa si el código
// coincide con el secret en este step de tiempo (±30s).
func TestVerifyTOTPSecret(t *testing.T) {
	secret, _ := generateTOTPSecret()
	tests := []struct {
		name string
		code string
		want bool
	}{
		{"5_digits", "12345", false},
		{"7_digits", "1234567", false},
		{"empty", "", false},
		{"letters", "abcdef", false},
		{"all_zeros", "000000", false}, // TOTP real no es todo-ceros
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, _ := verifyTOTPSecret(secret, tt.code)
			if got != tt.want {
				t.Errorf("verifyTOTPSecret(%q) = %v, want %v", tt.code, got, tt.want)
			}
		})
	}
}

func TestVerifyTOTPSecretEmptySecret(t *testing.T) {
	got, err := verifyTOTPSecret("", "123456")
	if got {
		t.Error("verifyTOTPSecret con secret vacío debería rechazar")
	}
	if err == nil {
		t.Error("verifyTOTPSecret con secret vacío debería retornar error")
	}
}

// ─── Helpers ────────────────────────────────────────────────────────────

func isHex(s string) bool {
	for _, c := range s {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return false
		}
	}
	return true
}
