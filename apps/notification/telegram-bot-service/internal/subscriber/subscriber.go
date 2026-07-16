// Package subscriber consume eventos de NATS y envía notificaciones a Telegram.
package subscriber

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/nats-io/nats.go"

	"github.com/tnsvt/telegram-bot-service/internal/models"
	"github.com/tnsvt/telegram-bot-service/internal/sender"
)

const (
	SubjectSend    = "notification.telegram.send"
	SubjectCommand = "platform.telegram.command"
)

// Subscriber maneja NATS → Telegram
type Subscriber struct {
	nats   *nats.Conn
	sender *sender.Sender
	log    interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// New crea el subscriber
func New(nc *nats.Conn, s *sender.Sender, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *Subscriber {
	return &Subscriber{
		nats:   nc,
		sender: s,
		log:    log,
	}
}

// Start comienza a escuchar
func (s *Subscriber) Start(ctx context.Context) error {
	sub, err := s.nats.Subscribe(SubjectSend, func(msg *nats.Msg) {
		var notif models.TelegramNotification
		if err := json.Unmarshal(msg.Data, &notif); err != nil {
			s.log.Error("Invalid notification", err)
			return
		}
		if notif.ChatID == 0 || notif.Text == "" {
			s.log.Warn("Missing chat_id or text")
			return
		}
		if err := s.sender.SendMessage(&notif); err != nil {
			s.log.Error("Send failed", err, "chat_id", notif.ChatID)
			return
		}
		s.log.Info("Sent", "chat_id", notif.ChatID, "text_len", len(notif.Text))
	})
	if err != nil {
		return fmt.Errorf("subscribe to %s: %w", SubjectSend, err)
	}

	cmdSub, err := s.nats.Subscribe(SubjectCommand, func(msg *nats.Msg) {
		var cmd models.CommandResponse
		if err := json.Unmarshal(msg.Data, &cmd); err != nil {
			s.log.Error("Invalid command", err)
			return
		}
		notif := &models.TelegramNotification{
			ChatID: cmd.ChatID,
			Text:   cmd.Text,
		}
		if err := s.sender.SendMessage(notif); err != nil {
			s.log.Error("Command send failed", err, "chat_id", cmd.ChatID)
		}
	})
	if err != nil {
		return fmt.Errorf("subscribe to %s: %w", SubjectCommand, err)
	}

	go func() {
		<-ctx.Done()
		sub.Unsubscribe()
		cmdSub.Unsubscribe()
	}()

	s.log.Info("Subscribed", "subjects", []string{SubjectSend, SubjectCommand})
	return nil
}
