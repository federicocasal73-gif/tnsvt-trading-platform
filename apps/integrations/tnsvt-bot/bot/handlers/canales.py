"""
Handler: /canales — Lista los canales Telegram configurados en config.json.
"""
import asyncio
import json
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_check import dm_only

logger = logging.getLogger("Bot.Handlers.Canales")

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT_DIR / "D:\\TradingBotMT5\\config.json"


def _read_config():
    try:
        # En Docker, config.json vive en D:\TradingBotMT5\config.json via bridge.
        # Mas robusto: usamos directamente via bridge-api
        import requests
        r = requests.get("http://localhost:8522/api/v1/bridge/config", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"bridge-api config unavailable: {e}")

    # Fallback: leer local
    try:
        cfg_path = Path(r"D:\TradingBotMT5\config.json")
        if cfg_path.exists():
            return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


@dm_only
async def canales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista los canales Telegram que el bot esta monitoreando."""
    try:
        user = update.effective_user
        logger.info(f"Comando /canales desde {user.username or user.id}")

        loop = asyncio.get_event_loop()
        cfg = await loop.run_in_executor(None, _read_config)

        channels_data = cfg.get("channels_data", []) or []
        if not channels_data:
            await update.message.reply_text(
                "⚠️ No hay canales configurados.\n"
                "Editá `D:\\TradingBotMT5\\config.json` y agregá entries en `channels_data`."
            )
            return

        text_lines = [f"📡 *Canales Monitoreados* ({len(channels_data)})\n"]
        for i, ch in enumerate(channels_data, 1):
            name = ch.get("name", "?")
            cid = ch.get("id", "?")
            tid = ch.get("topic_id")
            line = f"{i}. `{name}`"
            if tid is not None:
                line += f"  ·  topic={tid}"
            line += f"\n   ID: `{cid}`"
            text_lines.append(line)

        text_lines.append(f"\n_Lot mode: `{cfg.get('lot_mode', 'FIXED')}` · Lot size: `{cfg.get('lot_size', 0.01)}`_")
        text_lines.append(f"\nBot ejecutará trades solo en canales activos.")
        texto = "\n".join(text_lines)

        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en /canales: {e}")
        await update.message.reply_text("⚠️ Error al listar canales.")
