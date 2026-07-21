"""
Service: JBlanked API (Calendario Economico)
"""
import logging
import requests
from config import settings

logger = logging.getLogger("Services.JBlanked")


def get_calendar(limit: int = 7) -> list:
    """Obtiene eventos del calendario economico"""
    if not settings.JBLANKED_API_KEY:
        raise Exception("API Key de JBlanked no configurada")

    try:
        url = "https://www.jblanked.com/news/api/list/"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {settings.JBLANKED_API_KEY}",
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not data:
            return []

        return data[:limit]

    except requests.Timeout:
        logger.error("Timeout al obtener calendario")
        raise Exception("Timeout al conectar con JBlanked API")
    except requests.RequestException as e:
        logger.error(f"Error de conexion: {e}")
        raise Exception(f"Error de conexion: {e}")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise


def format_calendar(events: list) -> str:
    """Formatea los eventos para Telegram"""
    if not events:
        return "⚠️ No se encontraron eventos economicos"

    texto = "📅 *Calendario Economico*\n\n"

    for event in events:
        try:
            title = event.get("title", "Sin titulo")
            country = event.get("country", "N/A")
            date = event.get("date", "N/A")
            texto += f"🔹 {title} ({country}) - {date}\n"
        except Exception:
            continue

    return texto
