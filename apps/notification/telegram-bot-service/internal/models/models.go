// Package models define los tipos de notificaciones de Telegram.
package models

// Notificación a enviar por Telegram
type TelegramNotification struct {
	ChatID   int64  `json:"chat_id"`
	Text     string `json:"text"`
	ParseMode string `json:"parse_mode,omitempty"`
}

// Respuesta a un comando de Telegram
type CommandResponse struct {
	ChatID   int64  `json:"chat_id"`
	Command  string `json:"command"`
	Text     string `json:"text"`
	Args     string `json:"args,omitempty"`
}
