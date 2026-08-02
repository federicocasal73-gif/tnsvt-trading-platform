// Package trading contiene helpers compartidos entre los servicios de trading.
package trading

import (
	"hash/fnv"
	"strconv"
)

// MagicBase es la base para el magic number de TNSVT.
// Elegido para no colisionar con magic numbers típicos (que suelen ser
// valores redondos como 123456, 234000, etc).
const MagicBase int64 = 77000000

// MagicForAccount devuelve un magic number estable y único por account_id.
// La fórmula es: MagicBase + hash(account_id) % 100000.
//
// Esto garantiza:
//   - Determinístico: el mismo account_id siempre produce el mismo magic
//   - Rango acotado: 77000000-77099999 (compatible con magic int32 de MT5)
//   - Baja colisión: 100k valores distintos posibles
//   - Visible en el dashboard: 77000xxx siempre será "nuestro"
func MagicForAccount(accountID string) int64 {
	if accountID == "" {
		return MagicBase // fallback para señales legacy
	}
	h := fnv.New64a()
	_, _ = h.Write([]byte(accountID))
	return MagicBase + int64(h.Sum64()%100000)
}

// MagicForLogin devuelve un magic number basado en el login numérico de MT5.
// Útil como fallback si no hay account_id.
// Fórmula: MagicBase + login % 100000.
func MagicForLogin(login int64) int64 {
	if login <= 0 {
		return MagicBase
	}
	return MagicBase + login%100000
}

// MagicFromString parsea un magic number "77000xxx" o "123456" y devuelve int64.
// Si no se puede parsear, devuelve 0.
func MagicFromString(s string) int64 {
	if s == "" {
		return 0
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0
	}
	return v
}
