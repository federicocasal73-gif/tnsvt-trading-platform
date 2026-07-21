"""
Service: Trading Economics API
"""
import logging
import tradingeconomics as te
from config import settings

logger = logging.getLogger("Services.TradingEconomics")

_initialized = False


def init():
    """Inicializa la conexion con TradingEconomics"""
    global _initialized

    if not settings.TE_USERNAME:
        logger.warning("Credencial de TradingEconomics no configurada")
        _initialized = False
        return

    try:
        te.login(userkey=settings.TE_USERNAME)
        _initialized = True
        logger.info("TradingEconomics conectado exitosamente")
    except Exception as e:
        _initialized = False
        logger.warning(f"TradingEconomics no disponible: {e}")


def get_indicators(country: str = "ARG", limit: int = 5) -> list:
    """Obtiene indicadores economicos de un pais"""
    if not _initialized:
        raise Exception("TradingEconomics no inicializado")

    try:
        indicators = te.getIndicatorData(country=country)
        if indicators is None or len(indicators) == 0:
            return []
        return indicators[:limit]
    except Exception as e:
        logger.error(f"Error obteniendo indicadores de {country}: {e}")
        raise


def format_indicators(country: str, indicators: list) -> str:
    """Formatea los indicadores para Telegram"""
    if not indicators:
        return f"⚠️ No se encontraron indicadores para {country}"

    texto = f"📊 *Datos macroeconomicos de {country}*\n\n"

    for i in indicators:
        try:
            category = i.get("Category", "N/A")
            value = i.get("LatestValue", "N/A")
            unit = i.get("Unit", "")
            texto += f"▪️ {category} — {value} {unit}\n"
        except Exception:
            continue

    return texto
