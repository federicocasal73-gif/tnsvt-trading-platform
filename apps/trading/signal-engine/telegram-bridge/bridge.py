# TNSVT V2 - Telegram Bridge
# Conecta a canales de Telegram usando Telethon y envía señales al signal-engine

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp
from telethon import TelegramClient, events
from telethon.tl.custom.message import Message

# ─── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger("telegram-bridge")

# ─── Config ─────────────────────────────────────────────────────
TELETHON_API_ID = int(os.getenv("TELETHON_API_ID", "0"))
TELETHON_API_HASH = os.getenv("TELETHON_API_HASH", "")
TELETHON_PHONE = os.getenv("TELETHON_PHONE", "")
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "tnsvt_bridge")

# Canales a monitorear (comma-separated: name:telegram_id:trusted)
# Ejemplo: "VIP_Signals:-1001234567890:true,Free:-1009876543210:false"
CHANNELS_CONFIG = os.getenv("CHANNELS", "")

SIGNAL_ENGINE_URL = os.getenv("SIGNAL_ENGINE_URL", "http://signal-engine:8003")
SIGNAL_INGEST_API_KEY = os.getenv("SIGNAL_INGEST_API_KEY", "")

# ─── Helpers ───────────────────────────────────────────────────

async def send_to_signal_engine(session: aiohttp.ClientSession, payload: dict) -> dict:
    """Envía un raw signal al signal-engine via webhook."""
    url = f"{SIGNAL_ENGINE_URL}/internal/ingest/telegram"
    headers = {"Content-Type": "application/json"}
    if SIGNAL_INGEST_API_KEY:
        headers["X-API-Key"] = SIGNAL_INGEST_API_KEY

    try:
        async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
            body = await resp.json()
            return {"status": resp.status, "body": body}
    except asyncio.TimeoutError:
        return {"status": 408, "body": {"error": "timeout"}}
    except Exception as e:
        log.error(f"Failed to send to signal-engine: {e}")
        return {"status": 500, "body": {"error": str(e)}}


def parse_channel_config() -> list[dict]:
    """Parse CHANNELS env var into a list of channel configs."""
    channels = []
    if not CHANNELS_CONFIG:
        return channels

    for entry in CHANNELS_CONFIG.split(","):
        parts = entry.strip().split(":")
        if len(parts) >= 2:
            channel = {
                "name": parts[0],
                "telegram_id": int(parts[1]),
                "trusted": parts[2].lower() == "true" if len(parts) >= 3 else False,
            }
            channels.append(channel)
    return channels


# ─── Main ──────────────────────────────────────────────────────

async def main():
    if not TELETHON_API_ID or not TELETHON_API_HASH:
        log.error("TELETHON_API_ID and TELETHON_API_HASH are required")
        return

    channels = parse_channel_config()
    if not channels:
        log.warning("No channels configured (CHANNELS env var). Monitoring nothing.")

    log.info(f"Connecting to Telegram as {TELETHON_PHONE}...")
    client = TelegramClient(TELETHON_SESSION, TELETHON_API_ID, TELETHON_API_HASH)

    await client.start(phone=TELETHON_PHONE)
    log.info("Connected to Telegram")

    # Map telegram_id → channel_name para lookup
    channel_map = {ch["telegram_id"]: ch["name"] for ch in channels}
    channel_names = list(channel_map.values())

    log.info(f"Monitoring {len(channels)} channels: {channel_names}")

    aiohttp_session = aiohttp.ClientSession()

    # ─── Handler para nuevos mensajes ───────────────────────
    @client.on(events.NewMessage)
    async def on_new_message(event: events.NewMessage.Event):
        try:
            chat = await event.get_chat()
            chat_id = event.chat_id
            message: Message = event.message

            # Filtrar solo canales configurados
            if chat_id not in channel_map:
                return

            channel_name = channel_map[chat_id]
            text = message.text or message.raw_text or ""

            if not text.strip():
                return

            log.info(f"[{channel_name}] New message: {text[:80]}...")

            # Construir payload
            payload = {
                "channel_id": chat_id,
                "channel_name": channel_name,
                "message_id": message.id,
                "sender_id": message.sender_id,
                "text": text,
                "timestamp": message.date.isoformat() if message.date else datetime.utcnow().isoformat(),
            }

            if message.reply_to_msg_id:
                payload["reply_to_msg_id"] = message.reply_to_msg_id

            # Enviar al signal-engine
            result = await send_to_signal_engine(aiohttp_session, payload)
            status = result.get("status", 0)
            body = result.get("body", {})

            if status == 201:
                log.info(f"  → Accepted: signal_id={body.get('signal', {}).get('id', '?')}")
            elif status == 200 and body.get("skipped"):
                log.debug(f"  → Skipped (duplicate)")
            elif status == 422:
                log.info(f"  → Rejected: {body.get('reason', '?')}: {body.get('details', '')}")
            else:
                log.warning(f"  → Unexpected response: {status} {body}")

        except Exception as e:
            log.error(f"Error processing message: {e}", exc_info=True)

    # ─── Handler para mensajes editados ─────────────────────
    @client.on(events.MessageEdited)
    async def on_message_edited(event: events.MessageEdited.Event):
        # Tratar ediciones como mensajes nuevos (algunos canales editan para corregir SL/TP)
        await on_new_message(events.NewMessage.Event(event.message))

    log.info("Telegram bridge is running. Press Ctrl+C to stop.")
    log.info("Listening for new messages on configured channels...")

    try:
        # Run forever until disconnected
        await client.run_until_disconnected()
    finally:
        await aiohttp_session.close()
        log.info("Telegram bridge stopped")


if __name__ == "__main__":
    asyncio.run(main())