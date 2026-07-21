"""
Telegram channels scanner — extraído de dashboard.py:46 v13.0.

Permite escanear canales y tópicos (foros) del usuario autenticado en
Telegram usando Telethon. Independizado de Streamlit para poder ser
invocado desde el ScanWorker o desde cualquier script.

Devuelve estructura jerárquica:
[
  { "name": "Señales PRO", "id": -1003520242658, "is_forum": true,
    "topics": [ {"id": 1, "title": "Señales (Principal)"}, ... ] },
  ...
]
"""

import asyncio
import logging
import os
import sys
from typing import Any

from telethon import TelegramClient, functions, types

logger = logging.getLogger("bot.telegram_scan")


def _session_paths() -> tuple[str, str]:
    """Devuelve (session_base_path, session_file_path)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    session_name = "mitradingbot_session"
    session_file = os.path.join(base_dir, f"{session_name}.session")
    session_base = os.path.join(base_dir, session_name)
    return session_base, session_file


def is_authorized(api_id: str, api_hash: str) -> bool:
    """Chequea si la sesión Telethon está autorizada."""
    async def _check() -> bool:
        session_base, _ = _session_paths()
        client = TelegramClient(session_base, int(api_id), api_hash.strip())
        try:
            await client.connect()
            return await client.is_user_authorized()
        except Exception as e:
            logger.warning(f"is_authorized check failed: {e}")
            return False
        finally:
            if client.is_connected():
                await client.disconnect()
    return asyncio.run(_check())


async def _scan(api_id: str, api_hash: str, limit_per_channel: int = 5000) -> dict:
    """Realiza el scan. Devuelve {data: list} o {error: str}."""
    session_base, _ = _session_paths()
    client = TelegramClient(session_base, int(api_id), api_hash.strip())
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"error": "Sesión no válida. Reautenticar en panel Streamlit."}

        dialog_list: list[dict[str, Any]] = []
        all_dialogs: list[Any] = []
        async for d in client.iter_dialogs(limit=1000):
            all_dialogs.append(d)

        all_dialogs.sort(key=lambda x: (x.name or "").lower())

        for d in all_dialogs:
            ent = d.entity
            is_forum = getattr(ent, "forum", False) or (
                isinstance(ent, types.Channel) and ent.forum
            )
            item = {
                "name": d.name if d.name else "Sin Nombre",
                "id": d.id,
                "is_forum": is_forum,
                "topics": [],
            }

            if is_forum:
                try:
                    found_topics = {1: "Principal"}
                    input_peer = await client.get_input_entity(d.id)

                    active_ids = {1}
                    try:
                        async for m in client.iter_messages(d.id, limit=limit_per_channel):
                            if m.reply_to and m.reply_to.reply_to_top_id:
                                active_ids.add(m.reply_to.reply_to_top_id)
                            elif is_forum:
                                active_ids.add(1)
                            if m.action and isinstance(
                                m.action, types.MessageActionTopicCreate
                            ):
                                found_topics[m.id] = m.action.title
                    except Exception:
                        pass

                    if active_ids:
                        ids_to_resolve = list(active_ids)
                        for i in range(0, len(ids_to_resolve), 100):
                            try:
                                res = await client(
                                    functions.channels.GetForumTopicsByIDRequest(
                                        channel=input_peer,
                                        topics=ids_to_resolve[i:i + 100],
                                    )
                                )
                                for t in res.topics:
                                    if isinstance(t, types.ForumTopic):
                                        found_topics[t.id] = t.title
                            except Exception:
                                pass

                    try:
                        res = await client(
                            functions.channels.GetForumTopicsRequest(
                                channel=input_peer,
                                offset_date=0,
                                offset_id=0,
                                offset_topic=0,
                                limit=100,
                            )
                        )
                        for t in res.topics:
                            if isinstance(t, types.ForumTopic) and t.title:
                                if t.title.lower() != "general":
                                    found_topics[t.id] = t.title
                    except Exception:
                        pass

                    title_1 = "Señales (Principal)" if 1 in active_ids else "Principal"
                    final_topics = [{"id": 1, "title": title_1}]
                    ids_done = {1}
                    temp_list = []
                    for tid, tname in found_topics.items():
                        if tid not in ids_done:
                            temp_list.append({"id": tid, "title": tname})
                            ids_done.add(tid)
                    for tid in active_ids:
                        if tid not in ids_done:
                            temp_list.append(
                                {"id": tid, "title": f"Sub-canal #{tid} (Activo)"}
                            )
                            ids_done.add(tid)
                    temp_list.sort(key=lambda x: x["title"].lower())
                    final_topics.extend(temp_list)
                    item["topics"] = final_topics
                except Exception as e:
                    logger.warning(f"Topic scan error for {d.id}: {e}")
                    if not item["topics"]:
                        item["topics"].append({"id": 1, "title": "Principal"})

            dialog_list.append(item)
        return {"data": dialog_list}
    except Exception as e:
        logger.exception(f"Scan failed: {e}")
        return {"error": str(e)}
    finally:
        if client.is_connected():
            await client.disconnect()


def scan_channels(api_id: str, api_hash: str) -> dict:
    """API síncrona — entrypoint usado por ScanWorker."""
    if not api_id or not api_hash:
        return {"error": "api_id / api_hash no configurados"}
    return asyncio.run(_scan(api_id, api_hash))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    api_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("API_ID", "")
    api_hash = sys.argv[2] if len(sys.argv) > 2 else os.getenv("API_HASH", "")
    import json
    print(json.dumps(scan_channels(api_id, api_hash), indent=2, ensure_ascii=False))
