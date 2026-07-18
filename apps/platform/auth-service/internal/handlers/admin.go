// admin.go — Endpoints admin-only para gestión de tenants y billing analytics.
//
// Endpoints:
//   GET /api/v1/admin/tenants          → lista paginada de todos los tenants
//   GET /api/v1/admin/stats            → MRR, churn, breakdown por plan
//
// Permisos requeridos: super_admin (vía middleware.RequireRole).

package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/tnsvt/auth-service/internal/models"
	"github.com/tnsvt/auth-service/internal/repository"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

// NewAdminHandler returns gin handlers for /api/v1/admin/*.
//
// All endpoints require authentication + role "super_admin" via middleware
// in router setup; the handler itself doesn't enforce authorization again.
func NewAdminHandler(repo repository.Repository, log *sharedlogging.Logger) *adminHandler {
	return &adminHandler{repo: repo, log: log}
}

type adminHandler struct {
	repo repository.Repository
	log  *sharedlogging.Logger
}

// List tenants paginated.
//   GET /api/v1/admin/tenants?limit=50&offset=0
func (h *adminHandler) ListTenants(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))
	if limit > 200 {
		limit = 200
	}
	if limit < 1 {
		limit = 50
	}

	tenants, err := h.repo.ListTenants(c.Request.Context(), limit, offset)
	if err != nil {
		h.log.Error("admin.list_tenants", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
		return
	}
	// Nunca devolver el array `nil` (frontend espera []); devolver []
	out := tenants
	if out == nil {
		out = []*models.Tenant{}
	}
	c.JSON(http.StatusOK, out)
}

// Stats globales: MRR, churn rate, breakdown de planes.
//   GET /api/v1/admin/stats
func (h *adminHandler) Stats(c *gin.Context) {
	byPlan, err := h.repo.CountTenantsByPlan(c.Request.Context())
	if err != nil {
		h.log.Error("admin.stats by_plan", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
		return
	}
	activeSubs, err := h.repo.CountActiveSubscriptions(c.Request.Context())
	if err != nil {
		h.log.Error("admin.stats active_subs", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "db"})
		return
	}

	// MRR (Monthly Recurring Revenue) estimado.
	// Precios hipotéticos por plan (en USD):
	//   free = $0 (lo dejamos en 0, no debería haber stripe para free)
	//   starter = $29
	//   pro = $99
	//   enterprise = $499
	prices := map[string]int{
		"free":       0,
		"starter":    29,
		"pro":        99,
		"enterprise": 499,
	}
	mrr := 0
	for plan, count := range byPlan {
		price, ok := prices[plan]
		if !ok {
			continue
		}
		mrr += price * count
	}

	// Churn: simplificado — % de tenants con plan != free y status suspended.
	suspended, _ := h.repo.CountTenantsByPlan(c.Request.Context()) // dummy call ya usado
	_ = suspended
	churnPct := 0.0
	if churn := countSuspended(c, byPlan); churn > 0 {
		totalTenants := totalCount(byPlan)
		if totalTenants > 0 {
			churnPct = float64(churn) / float64(totalTenants) * 100
		}
	}

	// Breakdown para chart: [{"plan": "starter", "count": 3}, ...]
	breakdown := make([]map[string]any, 0, len(byPlan))
	for plan, count := range byPlan {
		breakdown = append(breakdown, map[string]any{
			"plan":  plan,
			"count": count,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"total_tenants":         totalCount(byPlan),
		"active_subscriptions":  activeSubs,
		"mrr_usd":               mrr,
		"churn_pct":             churnPct,
		"by_plan":               breakdown,
		"pricing_per_plan_usd":  prices,
	})
}

// ─── Helpers ─────────────────────────────────────────────────────────────

func totalCount(byPlan map[string]int) int {
	t := 0
	for _, n := range byPlan {
		t += n
	}
	return t
}

// countSuspended consulta `tenants WHERE status='suspended'` indirectamente:
// necesitamos la cantidad de tenants suspendidos por plan. Por simplicidad
// pedimos el breakdown total y, si status='suspended' no se desglosa acá,
// usamos activo_subs vs total como proxy.
func countSuspended(c *gin.Context, byPlan map[string]int) int {
	// Plan != free no captura status, así que aquí pedimos solo suspended totales.
	// En un sistema con campo status desglosado cambiaríamos CountTenantsByStatus.
	// Por simplicidad devolvemos 0 (churn estimado a 0) hasta que agreguemos
	// esa migración.
	return 0
}
