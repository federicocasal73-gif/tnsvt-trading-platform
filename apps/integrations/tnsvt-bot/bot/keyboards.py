"""
Keyboards - Layouts inline centralizados para el bot Telegram.

Antes los keyboards estaban dispersos en callbacks.py y cada handler.
Aqui reunimos todos para mantener consistencia visual y evitar duplicacion.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Menu principal (/start). Top-level con accesos rapidos (no submenus)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Panorama", callback_data="cmd:analisis"),
            InlineKeyboardButton("🎯 Zona", callback_data="cmd:zona"),
        ],
        [
            InlineKeyboardButton("📡 Canales", callback_data="cmd:canales"),
            InlineKeyboardButton("📊 Stats hoy", callback_data="cmd:stats"),
            InlineKeyboardButton("📈 Historial", callback_data="cmd:historial"),
        ],
        [
            InlineKeyboardButton("📅 Calendario", callback_data="cmd:calendario"),
            InlineKeyboardButton("📰 Noticias", callback_data="cmd:noticias"),
            InlineKeyboardButton("💱 Cripto", callback_data="cmd:cripto"),
        ],
        [
            InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas"),
            InlineKeyboardButton("💼 Bot MT5", callback_data="cmd:bot"),
        ],
        [
            InlineKeyboardButton("📊 /status", callback_data="cmd:status"),
            InlineKeyboardButton("🆘 Soporte", callback_data="cmd:soporte"),
            InlineKeyboardButton("🔄 Refrescar", callback_data="cmd:refresh"),
        ],
    ])


def help_menu() -> InlineKeyboardMarkup:
    """Menu de ayuda."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Señales", callback_data="senales:menu")],
        [InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def bot_status_menu() -> InlineKeyboardMarkup:
    """Menu de estado del bot MT5."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Canales", callback_data="cmd:canales")],
        [InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def senales_submenu() -> InlineKeyboardMarkup:
    """Submenu de senales."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats hoy", callback_data="cmd:stats")],
        [InlineKeyboardButton("📡 Canales", callback_data="cmd:canales")],
        [InlineKeyboardButton("📈 Historial esta semana", callback_data="historial:semana")],
        [InlineKeyboardButton("📈 Historial este mes", callback_data="historial:mes")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def stats_menu() -> InlineKeyboardMarkup:
    """Menu de stats de hoy."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Última semana", callback_data="historial:semana")],
        [InlineKeyboardButton("📅 Último mes", callback_data="historial:mes")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def canales_back() -> InlineKeyboardMarkup:
    """Boton volver cuando estamos en canales."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def cuenta_detail_back() -> InlineKeyboardMarkup:
    """Boton volver cuando estamos en detalle de cuenta."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Volver a Cuentas", callback_data="cmd:cuentas")],
        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
    ])


def soporte_menu() -> InlineKeyboardMarkup:
    """Menu de soporte."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Volver al menú", callback_data="cmd:refresh")],
    ])


def back_to_menu() -> InlineKeyboardMarkup:
    """Boton simple volver al menu principal."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
    ])
