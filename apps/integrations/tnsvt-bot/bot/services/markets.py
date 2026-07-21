"""
Service: Markets - Datos de mercados en tiempo real
"""
import logging
import requests

logger = logging.getLogger("Services.Markets")


def get_market_overview() -> str:
    """Obtiene resumen de mercados principales"""
    try:
        symbols = {
            "^GSPC": "S&P 500",
            "^IXIC": "Nasdaq",
            "^DJI": "Dow Jones",
            "^VIX": "VIX",
            "^FTSE": "FTSE 100",
            "^GDAXI": "DAX",
            "^FCHI": "CAC 40",
            "^IBEX": "IBEX 35",
        }

        texto = "📊 *Resumen de Mercados*\n\n"

        for symbol, name in symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    result = data["chart"]["result"][0]
                    meta = result["meta"]

                    price = meta.get("regularMarketPrice", 0)
                    prev_close = meta.get("previousClose", 0)

                    if prev_close > 0:
                        change_pct = ((price - prev_close) / prev_close) * 100
                        emoji = "🟢" if change_pct >= 0 else "🔴"
                        sign = "+" if change_pct >= 0 else ""
                        texto += f"{emoji} {name}: {sign}{change_pct:.2f}% ({price:,.2f})\n"
                    else:
                        texto += f"⚪ {name}: {price:,.2f}\n"

            except Exception:
                texto += f"⚪ {name}: No disponible\n"

        return texto

    except Exception as e:
        logger.error(f"Error obteniendo mercados: {e}")
        return "⚠️ Error al obtener datos de mercados"


def get_crypto_prices() -> str:
    """Obtiene precios de criptomonedas principales"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,solana,dogecoin,ripple",
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        texto = "₿ *Precios Criptomonedas*\n\n"

        cryptos = {
            "bitcoin": "Bitcoin",
            "ethereum": "Ethereum",
            "solana": "Solana",
            "dogecoin": "Dogecoin",
            "ripple": "XRP"
        }

        for crypto_id, name in cryptos.items():
            if crypto_id in data:
                price = data[crypto_id].get("usd", 0)
                change = data[crypto_id].get("usd_24h_change", 0)
                emoji = "🟢" if change >= 0 else "🔴"
                sign = "+" if change >= 0 else ""
                texto += f"{emoji} {name}: ${price:,.2f} ({sign}{change:.2f}%)\n"

        return texto

    except Exception as e:
        logger.error(f"Error obteniendo cripto: {e}")
        return "⚠️ Error al obtener precios de cripto"
