// Package cipher implementa encriptación AES-GCM para credenciales MT5.
//
// La master key se lee de MT5_PASSWORD_KEY en el .env (debe ser hex-encoded,
// 32 bytes = 64 hex chars). Si no está configurada, se deriva de JWT_SECRET
// (degración). En producción, MT5_PASSWORD_KEY es OBLIGATORIA.
package cipher

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"os"
)

// Cipher encapsula AES-GCM con una master key de 32 bytes.
type Cipher struct {
	gcm cipher.AEAD
}

// New crea un cipher desde la master key (hex-encoded).
// Si envKey está vacío, intenta derivar de MT5_PASSWORD_KEY / JWT_SECRET.
func New(envKey string) (*Cipher, error) {
	keyHex := envKey
	if keyHex == "" {
		keyHex = os.Getenv("MT5_PASSWORD_KEY")
	}
	if keyHex == "" {
		keyHex = os.Getenv("JWT_SECRET")
	}
	if keyHex == "" {
		return nil, errors.New("MT5_PASSWORD_KEY / JWT_SECRET not set; cannot initialize cipher")
	}

	keyBytes, err := hex.DecodeString(keyHex)
	if err != nil {
		// No es hex: derivamos con SHA-256 para tener 32 bytes
		h := sha256.Sum256([]byte(keyHex))
		keyBytes = h[:]
	}

	// Asegurar 32 bytes (AES-256)
	if len(keyBytes) > 32 {
		keyBytes = keyBytes[:32]
	} else if len(keyBytes) < 32 {
		// Pad con SHA-256
		h := sha256.Sum256(keyBytes)
		keyBytes = append(keyBytes, h[:32-len(keyBytes)]...)
	}

	block, err := aes.NewCipher(keyBytes)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	return &Cipher{gcm: gcm}, nil
}

// Encrypt encripta plaintext y devuelve nonce||ciphertext (hex-encoded).
func (c *Cipher) Encrypt(plaintext string) (string, error) {
	nonce := make([]byte, c.gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ct := c.gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return hex.EncodeToString(ct), nil
}

// Decrypt desencripta nonce||ciphertext (hex-encoded).
func (c *Cipher) Decrypt(encoded string) (string, error) {
	raw, err := hex.DecodeString(encoded)
	if err != nil {
		return "", err
	}
	ns := c.gcm.NonceSize()
	if len(raw) < ns {
		return "", errors.New("ciphertext too short")
	}
	nonce, ct := raw[:ns], raw[ns:]
	pt, err := c.gcm.Open(nil, nonce, ct, nil)
	if err != nil {
		return "", err
	}
	return string(pt), nil
}
