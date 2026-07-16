// Package models define los perfiles y preferencias de usuario.
package models

import (
	"time"

	"github.com/google/uuid"
)

// UserProfile representa el perfil extendido del usuario.
type UserProfile struct {
	UserID         uuid.UUID              `json:"user_id"`
	TenantID       uuid.UUID              `json:"tenant_id"`
	FullName       string                 `json:"full_name"`
	AvatarURL      string                 `json:"avatar_url,omitempty"`
	Timezone       string                 `json:"timezone"`
	Language       string                 `json:"language"`
	Phone          string                 `json:"phone,omitempty"`
	Preferences    map[string]interface{} `json:"preferences,omitempty"`
	NotifySettings map[string]interface{} `json:"notify_settings,omitempty"`
	CreatedAt      time.Time              `json:"created_at"`
	UpdatedAt      time.Time              `json:"updated_at"`
}

// CreateProfileRequest payload
type CreateProfileRequest struct {
	FullName  string `json:"full_name"`
	Timezone  string `json:"timezone"`
	Language  string `json:"language"`
	Phone     string `json:"phone,omitempty"`
	AvatarURL string `json:"avatar_url,omitempty"`
}

// UpdateProfileRequest payload
type UpdateProfileRequest struct {
	FullName       *string                `json:"full_name,omitempty"`
	AvatarURL      *string                `json:"avatar_url,omitempty"`
	Timezone       *string                `json:"timezone,omitempty"`
	Language       *string                `json:"language,omitempty"`
	Phone          *string                `json:"phone,omitempty"`
	Preferences    map[string]interface{} `json:"preferences,omitempty"`
	NotifySettings map[string]interface{} `json:"notify_settings,omitempty"`
}
