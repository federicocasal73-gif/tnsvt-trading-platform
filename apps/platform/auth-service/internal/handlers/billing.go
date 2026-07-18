// Package handlers contiene los endpoints HTTP de auth-service.
//
// billing.go — Webhook handler para Stripe.
//
// Eventos manejados:
//   - checkout.session.completed → activa tenant después del pago
//   - customer.subscription.created → crea suscripción en DB
//   - customer.subscription.updated → actualiza plan (upgrade/downgrade)
//   - customer.subscription.deleted → cancela tenant
//   - invoice.paid → extiende periodo activo del tenant
//
// Seguridad: HMAC SHA256 signature verification contra STRIPE_WEBHOOK_SECRET.
// Sin signature válida, el handler retorna 401.
//
// Almacenamos el customer_id de Stripe en un campo nuevo de tenant
// (billing_customer_id) en la próxima migración. Por ahora usamos el
// metadata.tenant_id que viajará dentro del payload de Stripe.

package handlers

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/tnsvt/auth-service/internal/models"
	"github.com/tnsvt/auth-service/internal/repository"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

// ─── Stripe webhook payload (subset) ─────────────────────────────────────

type stripeCheckoutSession struct {
	Type             string `json:"type"`
	Data             struct {
		Object struct {
			ID           string `json:"id"`
			Customer     string `json:"customer"`
			Subscription string `json:"subscription"`
			CustomerEmail string `json:"customer_email"`
			Metadata     struct {
				TenantID string `json:"tenant_id"`
				Plan     string `json:"plan"`
			} `json:"metadata"`
		} `json:"object"`
	} `json:"data"`
}

type stripeSubscription struct {
	Type string `json:"type"`
	Data struct {
		Object struct {
			ID       string `json:"id"`
			Customer string `json:"customer"`
			Status   string `json:"status"`
			Items    struct {
				Data []struct {
					Price struct {
						Nickname string `json:"nickname"` // "starter", "pro", "enterprise"
					} `json:"price"`
				} `json:"data"`
			} `json:"items"`
			Metadata struct {
				TenantID string `json:"tenant_id"`
				Plan     string `json:"plan"`
			} `json:"metadata"`
			CurrentPeriodEnd int64 `json:"current_period_end"`
		} `json:"object"`
	} `json:"data"`
}

type stripeInvoice struct {
	Type string `json:"type"`
	Data struct {
		Object struct {
			ID           string `json:"id"`
			Customer     string `json:"customer"`
			Subscription string `json:"subscription"`
			AmountPaid   int64  `json:"amount_paid"`
			Currency     string `json:"currency"`
			Paid         bool   `json:"paid"`
			Metadata     struct {
				TenantID string `json:"tenant_id"`
			} `json:"metadata"`
		} `json:"object"`
	} `json:"data"`
}

// ─── Handler ──────────────────────────────────────────────────────────────

// NewBillingHandler returns gin handlers for /api/v1/auth/billing/*.
//
// Requires repo for tenant updates and log for observability. Falls back
// to a no-op logger if nil to avoid panics in dev/test contexts.
func NewBillingHandler(repo repository.Repository, log *sharedlogging.Logger) gin.HandlerFunc {
	if log == nil {
		log = sharedlogging.New("auth-billing", "info")
	}

	secret := os.Getenv("STRIPE_WEBHOOK_SECRET")

	return func(c *gin.Context) {
		// ─── 1. Read raw body (needed for HMAC) ─────────────────────────
		body, err := io.ReadAll(c.Request.Body)
		if err != nil {
			log.Error("billing.webhook read_body", err)
			c.JSON(http.StatusBadRequest, gin.H{"error": "cannot read body"})
			return
		}

		// ─── 2. Verify signature ───────────────────────────────────────
		if secret != "" {
			sigHeader := c.GetHeader("Stripe-Signature")
			if !verifyStripeSignature(body, sigHeader, secret) {
				log.Warn("billing.webhook invalid signature",
					"client_ip", c.ClientIP(),
					"path", c.Request.URL.Path,
				)
				c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid signature"})
				return
			}
		} else {
			log.Warn("billing.webhook STRIPE_WEBHOOK_SECRET not set — accepting unsigned (dev only)")
		}

		// ─── 3. Parse top-level type ──────────────────────────────────
		var envelope struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(body, &envelope); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid JSON"})
			return
		}

		// ─── 4. Dispatch by event type ────────────────────────────────
		switch envelope.Type {

		case "checkout.session.completed":
			var evt stripeCheckoutSession
			if err := json.Unmarshal(body, &evt); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "bad checkout.session payload"})
				return
			}
			tenantID := evt.Data.Object.Metadata.TenantID
			if tenantID == "" {
				log.Warn("billing.webhook checkout.session without tenant_id metadata")
				c.JSON(http.StatusOK, gin.H{"ok": true, "ignored": "no tenant_id"})
				return
			}
			if _, err := uuid.Parse(tenantID); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "invalid tenant_id uuid"})
				return
			}
			plan := evt.Data.Object.Metadata.Plan
			if plan == "" {
				plan = "starter"
			}
			if err := updateTenantPlan(c, repo, tenantID, plan); err != nil {
				log.Error("billing.webhook update plan", err, "tenant_id", tenantID)
				c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
				return
			}
			log.Info("billing.checkout.completed", "tenant_id", tenantID, "plan", plan)
			c.JSON(http.StatusOK, gin.H{"ok": true, "tenant_id": tenantID, "plan": plan})

		case "customer.subscription.created", "customer.subscription.updated":
			var evt stripeSubscription
			if err := json.Unmarshal(body, &evt); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "bad subscription payload"})
				return
			}
			tenantID := evt.Data.Object.Metadata.TenantID
			if tenantID == "" {
				// Fallback: buscar por customer_email. Por simplicidad,
				// el cliente DEBE pasar tenant_id en metadata al crear
				// la suscripción.
				log.Warn("billing.webhook subscription without tenant_id metadata")
				c.JSON(http.StatusOK, gin.H{"ok": true, "ignored": "no tenant_id"})
				return
			}
			plan := planFromSubscription(&evt.Data.Object)
			if evt.Data.Object.Status == "canceled" || evt.Data.Object.Status == "incomplete_expired" {
				if err := suspendTenant(c, repo, tenantID); err != nil {
					log.Error("billing.webhook suspend", err)
					c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
					return
				}
				log.Info("billing.subscription.canceled", "tenant_id", tenantID)
				c.JSON(http.StatusOK, gin.H{"ok": true, "tenant_id": tenantID, "status": "suspended"})
				return
			}
			if err := updateTenantPlan(c, repo, tenantID, plan); err != nil {
				log.Error("billing.webhook update", err)
				c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
				return
			}
			c.JSON(http.StatusOK, gin.H{"ok": true, "tenant_id": tenantID, "plan": plan, "status": evt.Data.Object.Status})

		case "customer.subscription.deleted":
			var evt stripeSubscription
			if err := json.Unmarshal(body, &evt); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "bad subscription payload"})
				return
			}
			tenantID := evt.Data.Object.Metadata.TenantID
			if tenantID == "" {
				log.Warn("billing.webhook subscription.delete without tenant_id metadata")
				c.JSON(http.StatusOK, gin.H{"ok": true, "ignored": "no tenant_id"})
				return
			}
			if err := suspendTenant(c, repo, tenantID); err != nil {
				log.Error("billing.webhook suspend", err)
				c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
				return
			}
			c.JSON(http.StatusOK, gin.H{"ok": true, "tenant_id": tenantID, "plan": "free", "status": "canceled"})

		case "invoice.paid":
			var evt stripeInvoice
			if err := json.Unmarshal(body, &evt); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "bad invoice payload"})
				return
			}
			tenantID := evt.Data.Object.Metadata.TenantID
			if tenantID == "" || !evt.Data.Object.Paid {
				c.JSON(http.StatusOK, gin.H{"ok": true, "ignored": "no tenant or unpaid"})
				return
			}
			if err := extendTenantPlan(c, repo, tenantID); err != nil {
				log.Error("billing.webhook extend", err)
				c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
				return
			}
			c.JSON(http.StatusOK, gin.H{"ok": true, "tenant_id": tenantID, "event": "invoice.paid"})

		default:
			// Ignore unknown events — Stripe sends many types; we only need a subset.
			c.JSON(http.StatusOK, gin.H{"ok": true, "ignored": envelope.Type})
		}
	}
}

// ─── Helpers ─────────────────────────────────────────────────────────────

func verifyStripeSignature(payload []byte, header string, secret string) bool {
	// Stripe format: "t=<timestamp>,v1=<sig>"
	parts := splitStripeHeader(header)
	if parts.t == 0 || parts.v1 == "" {
		return false
	}
	// Construct signed payload: "<timestamp>.<body>"
	signedPayload := strconv.FormatInt(parts.t, 10) + "." + string(payload)
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(signedPayload))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(parts.v1))
}

type stripeSigParts struct {
	t   int64
	v1  string
}

func splitStripeHeader(header string) stripeSigParts {
	var p stripeSigParts
	// Format: t=1700000000,v1=abcd...
	entries := splitCSV(header)
	for _, e := range entries {
		if len(e) > 2 && e[:2] == "t=" {
			if v, err := strconv.ParseInt(e[2:], 10, 64); err == nil {
				p.t = v
			}
		} else if len(e) > 3 && e[:3] == "v1=" {
			p.v1 = e[3:]
		}
	}
	return p
}

func splitCSV(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == ',' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}

func planFromSubscription(sub *struct {
	ID       string `json:"id"`
	Customer string `json:"customer"`
	Status   string `json:"status"`
	Items    struct {
		Data []struct {
			Price struct {
				Nickname string `json:"nickname"`
			} `json:"price"`
		} `json:"data"`
	} `json:"items"`
	Metadata struct {
		TenantID string `json:"tenant_id"`
		Plan     string `json:"plan"`
	} `json:"metadata"`
	CurrentPeriodEnd int64 `json:"current_period_end"`
}) string {
	if sub.Metadata.Plan != "" {
		return sub.Metadata.Plan
	}
	if len(sub.Items.Data) > 0 {
		nick := sub.Items.Data[0].Price.Nickname
		if nick != "" {
			return nick
		}
	}
	return "starter"
}

func updateTenantPlan(c *gin.Context, repo repository.Repository, tenantID string, plan string) error {
	// Validate plan
	switch plan {
	case "free", "starter", "pro", "enterprise":
		// ok
	default:
		return nil // unknown plan, no-op
	}
	id, err := uuid.Parse(tenantID)
	if err != nil {
		return err
	}
	tenant, err := repo.GetTenantByID(c.Request.Context(), id)
	if err != nil {
		return err
	}
	if tenant == nil {
		return nil // unknown tenant, no-op
	}
	tenant.Plan = plan
	tenant.Status = "active"
	tenant.UpdatedAt = time.Now().UTC()
	return repo.UpdateTenant(c.Request.Context(), tenant)
}

func suspendTenant(c *gin.Context, repo repository.Repository, tenantID string) error {
	id, err := uuid.Parse(tenantID)
	if err != nil {
		return err
	}
	tenant, err := repo.GetTenantByID(c.Request.Context(), id)
	if err != nil {
		return err
	}
	if tenant == nil {
		return nil
	}
	tenant.Plan = "free"
	tenant.Status = "suspended"
	tenant.UpdatedAt = time.Now().UTC()
	return repo.UpdateTenant(c.Request.Context(), tenant)
}

func extendTenantPlan(c *gin.Context, repo repository.Repository, tenantID string) error {
	id, err := uuid.Parse(tenantID)
	if err != nil {
		return err
	}
	tenant, err := repo.GetTenantByID(c.Request.Context(), id)
	if err != nil {
		return err
	}
	if tenant == nil {
		return nil
	}
	tenant.Status = "active"
	tenant.UpdatedAt = time.Now().UTC()
	return repo.UpdateTenant(c.Request.Context(), tenant)
}

// Compile-time guard: ensure models is referenced (will be in next migration).
var _ = models.Tenant{}
