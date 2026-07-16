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
		{"valid_strong", "MyStr0ngPass99", nil},
		{"valid_with_symbols", "Passw0rd!@#$%", nil},
		{"too_short", "Ab1", ErrWeakPassword},
		{"empty", "", ErrWeakPassword},
		{"no_upper", "mystr0ngpass99", ErrWeakPassword},
		{"no_lower", "MYSTR0NGPASS99", ErrWeakPassword},
		{"no_digit", "MyStrongPassword", ErrWeakPassword},
		{"only_letters_long", "abcdefghijklmnop", ErrWeakPassword},
		{"exactly_min_length_valid", "Abcdefgh1jkl", nil}, // 12 chars, has upper+lower+digit
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
		{"unicode_kept_out", "Tñádíng 2026", "tdng-2026"}, // non-ASCII chars stripped
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

func TestVerifyTOTPSecret(t *testing.T) {
	tests := []struct {
		code string
		want bool
	}{
		{"123456", true},
		{"000000", true},
		{"999999", true},
		{"12345", false},  // 5 digits
		{"1234567", false}, // 7 digits
		{"", false},
		{"abc123", false},
	}

	for _, tt := range tests {
		t.Run(tt.code, func(t *testing.T) {
			got := verifyTOTPSecret("dummy-secret", tt.code)
			if got != tt.want {
				t.Errorf("verifyTOTPSecret(%q) = %v, want %v", tt.code, got, tt.want)
			}
		})
	}
}

func TestGenerateTOTPSecret(t *testing.T) {
	s := generateTOTPSecret()
	if s == "" {
		t.Fatal("generateTOTPSecret returned empty")
	}
	// Must be a valid UUID format
	if len(s) != 36 {
		t.Errorf("generateTOTPSecret length = %d, want 36", len(s))
	}
	if strings.Count(s, "-") != 4 {
		t.Errorf("generateTOTPSecret has %d dashes, want 4 (UUID format)", strings.Count(s, "-"))
	}

	// Two calls should give different secrets
	s2 := generateTOTPSecret()
	if s == s2 {
		t.Error("generateTOTPSecret returned same value twice (should be random)")
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