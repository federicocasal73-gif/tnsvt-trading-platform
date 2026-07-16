// Package sender envía mensajes a Telegram vía Bot API HTTP.
package sender

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/tnsvt/telegram-bot-service/internal/models"
)

// Sender envía mensajes a Telegram
type Sender struct {
	botToken string
	client   *http.Client
	log      interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// New crea el sender
func New(botToken string, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *Sender {
	return &Sender{
		botToken: botToken,
		client: &http.Client{
			Timeout: 10 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:    5,
				IdleConnTimeout: 30 * time.Second,
			},
		},
		log: log,
	}
}

// SendMessage envía un mensaje a un chat de Telegram
func (s *Sender) SendMessage(notif *models.TelegramNotification) error {
	body, _ := json.Marshal(map[string]interface{}{
		"chat_id":    notif.ChatID,
		"text":       notif.Text,
		"parse_mode": "HTML",
	})

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", s.botToken)
	resp, err := s.client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("telegram API call: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("telegram API error: status=%d", resp.StatusCode)
	}
	return nil
}
