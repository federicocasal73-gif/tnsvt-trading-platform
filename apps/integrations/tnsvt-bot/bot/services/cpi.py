"""
Service: CPI Data - Datos reales del IPC de EEUU via BLS API (gratuita, sin auth)
"""
import logging
import requests
from datetime import datetime

logger = logging.getLogger("Services.CPI")

# BLS series ID - CPI-U, All items, U.S. city average, not seasonally adjusted
CPI_SERIES = "CUSR0000SA0"


def get_cpi_data() -> dict:
    """Obtiene los ultimos datos del CPI desde BLS.gov (API v1, sin auth)."""
    try:
        url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
        # Fetch 2 years to calculate YoY%
        payload = {
            "seriesid": [CPI_SERIES],
            "startyear": str(datetime.now().year - 2),
            "endyear": str(datetime.now().year),
        }

        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "REQUEST_SUCCEEDED":
            logger.warning(f"BLS API status: {data.get('status')}")
            return _fallback_data()

        series_list = data.get("Results", {}).get("series", [])
        if not series_list:
            return _fallback_data()

        cpi_values = []
        for series in series_list:
            for item in series.get("data", []):
                year = item.get("year", "")
                period = item.get("period", "")
                value = item.get("value", "")
                footnotes = item.get("footnotes", [])

                is_preliminary = any(
                    fn.get("text") == "Preliminary" for fn in footnotes
                )

                cpi_values.append({
                    "year": year,
                    "period": period,
                    "value": value,
                    "preliminary": is_preliminary,
                })

        cpi_values.sort(key=lambda x: (x["year"], x["period"]), reverse=True)

        latest = cpi_values[0] if cpi_values else None

        # Calculate YoY%: find same month last year
        yoy_pct = None
        yoy_period = None
        if latest and latest["period"].startswith("M"):
            current_val = float(latest["value"])
            current_period = latest["period"]
            current_year = int(latest["year"])

            for entry in cpi_values:
                if entry["period"] == current_period and int(entry["year"]) == current_year - 1:
                    prev_val = float(entry["value"])
                    if prev_val > 0:
                        yoy_pct = round(((current_val / prev_val) - 1) * 100, 2)
                        yoy_period = _format_period(entry["period"], entry["year"])
                    break

        # Calculate MoM%: find previous month
        mom_pct = None
        if latest and len(cpi_values) > 1:
            current_val = float(latest["value"])
            for entry in cpi_values[1:]:
                if entry["period"].startswith("M") and entry["value"]:
                    prev_val = float(entry["value"])
                    if prev_val > 0:
                        mom_pct = round(((current_val / prev_val) - 1) * 100, 2)
                    break

        return {
            "latest_cpi": latest.get("value") if latest else None,
            "latest_period": _format_period(latest.get("period", ""), latest.get("year", "")) if latest else None,
            "latest_yoy": yoy_pct,
            "yoy_period": yoy_period,
            "latest_mom": mom_pct,
            "preliminary": latest.get("preliminary", False) if latest else False,
            "trend": _calculate_trend(cpi_values[:6]),
            "recent": cpi_values[:6],
            "source": "BLS.gov",
        }

    except Exception as e:
        logger.error(f"Error obteniendo CPI de BLS: {e}")
        return _fallback_data()


def _format_period(period: str, year: str) -> str:
    """Convierte M01..M12 a nombre de mes."""
    months = {
        "M01": "Enero", "M02": "Febrero", "M03": "Marzo",
        "M04": "Abril", "M05": "Mayo", "M06": "Junio",
        "M07": "Julio", "M08": "Agosto", "M09": "Septiembre",
        "M10": "Octubre", "M11": "Noviembre", "M12": "Diciembre",
    }
    month_name = months.get(period, period)
    return f"{month_name} {year}"


def _calculate_trend(values: list) -> str:
    """Calcula la tendencia del CPI (ultimas 6 lecturas)."""
    if len(values) < 2:
        return "Sin datos suficientes"

    try:
        nums = [float(v["value"]) for v in values]
        diffs = [nums[i] - nums[i + 1] for i in range(len(nums) - 1)]
        avg_change = sum(diffs) / len(diffs)

        if avg_change > 0.3:
            return "↗️ En aumento"
        elif avg_change < -0.3:
            return "↘️ En descenso"
        else:
            return "→ Estable"
    except (ValueError, ZeroDivisionError):
        return "Sin tendencia clara"


def format_cpi_message(data: dict) -> str:
    """Formatea los datos del CPI para Telegram."""
    latest_cpi = data.get("latest_cpi", "?")
    latest_period = data.get("latest_period", "?")
    latest_yoy = data.get("latest_yoy")
    latest_mom = data.get("latest_mom")
    preliminary = data.get("preliminary", False)
    trend = data.get("trend", "?")
    recent = data.get("recent", [])

    prelim_tag = " (Preliminar)" if preliminary else ""

    yoy_str = f"{latest_yoy:+.2f}%" if latest_yoy is not None else "N/D"
    mom_str = f"{latest_mom:+.2f}%" if latest_mom is not None else "N/D"

    texto = f"""📊 *IPC de EEUU (CPI-U)*{prelim_tag}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *Valor actual:*
• IPC: `{latest_cpi}` — {latest_period}
• Mensual (MoM): `{mom_str}`
• Anual (YoY): `{yoy_str}`

📈 *Tendencia (ultimos 6 meses):*
• {trend}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if recent:
        texto += "\n📋 *Historial reciente:*\n"
        for entry in recent[:6]:
            month = _format_period(entry.get("period", ""), entry.get("year", ""))
            value = entry.get("value", "?")
            texto += f"   • {month}: `{value}`\n"

    texto += f"\n_Fuente: {data.get('source', 'BLS.gov')}_"
    return texto


def _fallback_data() -> dict:
    """Datos de fallback cuando BLS no responde."""
    return {
        "latest_cpi": None,
        "latest_period": None,
        "latest_yoy": None,
        "yoy_period": None,
        "preliminary": False,
        "trend": "Sin datos disponibles",
        "recent": [],
        "source": "BLS.gov (sin conexion)",
        "error": True,
    }
