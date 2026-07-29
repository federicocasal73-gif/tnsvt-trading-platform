"""
TNSVT Constants — Brand assets shared across bot handlers.

Centraliza el disclaimer, la cobertura de instrumentos y textos de marca
para mantener consistencia visual y de messaging en todo el bot.
"""

TNSVT_BRAND_LINE = "Terminal Financiera Pro TNSVT"

TNSVT_DISCLAIMER = (
    "⚠️ *Terminal Financiera Pro TNSVT — Señales automatizadas, "
    "no asesoramiento financiero.* El trading de derivados y CFDs "
    "conlleva riesgo significativo de pérdida. Resultados pasados "
    "no garantizan resultados futuros. Operá bajo tu propio riesgo."
)

TNSVT_SHORT_DISCLAIMER = (
    "⚠️ _Señales automatizadas, no asesoramiento financiero. "
    "El trading conlleva riesgo de pérdida._"
)

TNSVT_COVERAGE = {
    "forex": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
        "NZDUSD", "EURJPY", "GBPJPY",
    ],
    "indices": [
        "NAS100", "US30", "US500", "SPX", "NDX", "GER40", "UK100",
    ],
    "crypto": [
        "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD",
    ],
    "commodities": [
        "XAUUSD", "XAGUSD", "WTI", "BRENT",
    ],
}

TNSVT_COVERAGE_FOOTER = (
    "📡 *Cobertura multi-activo:*\n"
    "• 💱 Forex: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF\n"
    "• 📊 Índices: NAS100, US30, US500, SPX, NDX\n"
    "• 🪙 Cripto: BTCUSD, ETHUSD, SOLUSD\n"
    "• 🥇 Commodities: XAUUSD, XAGUSD, WTI, BRENT"
)

POLL_INSTRUMENTS = ["BTCUSD", "XAUUSD", "EURUSD", "DXY", "NAS100"]

POLL_OPTIONS = ["🟢 Alcista", "🔴 Bajista", "🟡 Rango", "⚪ Afuera"]

WEEKLY_POLL_HOUR = 9
WEEKLY_CALENDAR_HOUR = 9
WEEKLY_CALENDAR_MINUTE = 30

WELCOME_KEYBOARD_ROWS = [
    [
        ("📋 Menú Principal", "cmd:refresh"),
    ],
    [
        ("📊 Dashboard", "cmd:status"),
        ("🆘 Soporte", "cmd:soporte"),
    ],
]
