"""
Signal Copier - Filtro de Noticias Economicas
Bloquea trades antes/despues de noticias de alto impacto
"""
import os
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("SignalCopier.NewsFilter")

ROOT_DIR = Path(__file__).parent.parent


class NewsFilter:
    """Filtra trades basado en calendario economico"""

    HIGH_IMPACT_KEYWORDS = [
        "NFP", "NON-FARM", "PAYROLL", "CPI", "PPI", "GDP",
        "FOMC", "FED", "INTEREST RATE", "RATE DECISION",
        "RETAIL SALES", "PMI", "ISM", "UNEMPLOYMENT",
        "INFLATION", "CONSUMER PRICE", "PRODUCER PRICE",
        "TRADE BALANCE", "HOUSING STARTS", "BUILDING PERMITS",
        "DURABLE GOODS", "INITIAL JOBLESS", "CONTINUING CLAIMS",
        "FED CHAIR", "POWELL", "YELLEN", "LAGARDE",
        "ECB", "BOJ", "BOE", "SNB", "RBA", "RBNZ",
    ]

    def __init__(self):
        self.reload_config()
        self.upcoming_events = []
        self._last_fetch = None
        self._fetch_interval = 300  # 5 minutos
        self._fetch_lock = threading.Lock()
        self._te_error_logged = False

    def reload_config(self):
        """Recarga configuracion desde .env"""
        from config import settings
        self.enabled = settings.NEWS_FILTER_ENABLED
        self.minutes_before = settings.NEWS_FILTER_MINUTES_BEFORE
        self.minutes_after = settings.NEWS_FILTER_MINUTES_AFTER
        self.high_impact_only = settings.NEWS_FILTER_HIGH_IMPACT_ONLY
        logger.info(
            f"NewsFilter config: enabled={self.enabled}, "
            f"before={self.minutes_before}min, after={self.minutes_after}min"
        )

    def should_block_trade(self) -> tuple:
        """Verifica si hay noticias proximas que bloquean trades"""
        if not self.enabled:
            return False, ""

        self._fetch_upcoming_events()

        now = datetime.now()
        for event in self.upcoming_events:
            event_time = event.get("date")
            if not event_time:
                continue

            try:
                diff_minutes = (event_time - now).total_seconds() / 60
            except Exception:
                continue

            if -self.minutes_after <= diff_minutes <= self.minutes_before:
                return True, (
                    f"Noticia: {event['name']} ({event['country']}) "
                    f"en {int(abs(diff_minutes))} minutos"
                )

        return False, ""

    def get_positions_to_close(self) -> list:
        """Retorna posiciones que deben cerrarse antes de noticias"""
        if not self.enabled:
            return []

        self._fetch_upcoming_events()

        positions_to_close = []
        now = datetime.now()

        for event in self.upcoming_events:
            event_time = event.get("date")
            if not event_time:
                continue

            try:
                diff_minutes = (event_time - now).total_seconds() / 60
            except Exception:
                continue

            if 0 < diff_minutes <= self.minutes_before:
                symbol = self._event_to_symbol(event)
                if symbol:
                    positions_to_close.append({
                        "symbol": symbol,
                        "reason": f"News: {event['name']} en {int(diff_minutes)}min"
                    })

        return positions_to_close

    def _fetch_upcoming_events(self):
        """Obtiene eventos del calendario economico (thread-safe)"""
        now = datetime.now()

        with self._fetch_lock:
            if self._last_fetch and (now - self._last_fetch).seconds < self._fetch_interval:
                return

        try:
            self._fetch_from_tradingeconomics()
        except Exception as e:
            if not self._te_error_logged:
                logger.warning(f"TradingEconomics no disponible, usando fallback: {e}")
            else:
                logger.debug(f"TradingEconomics fallback (silenciado): {e}")
            self._fetch_fallback()

        with self._fetch_lock:
            self._last_fetch = now

    def _fetch_from_tradingeconomics(self):
        """Obtiene eventos de TradingEconomics API"""
        from config import settings

        if not settings.TE_USERNAME or not settings.TE_PASSWORD:
            raise ValueError("TradingEconomics credentials not configured")

        try:
            import sys
            sys.path.insert(0, str(ROOT_DIR))
            from tradingeconomics import login, getCalendarData

            login(f"{settings.TE_USERNAME}:{settings.TE_PASSWORD}")

            today = datetime.now().strftime("%Y-%m-%d")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

            importance = "3" if self.high_impact_only else None

            data = getCalendarData(
                initDate=today,
                endDate=tomorrow,
                importance=importance,
                output_type="raw"
            )

            self.upcoming_events = self._parse_events(data)
            self._te_error_logged = False
            logger.info(f"Eventos cargados: {len(self.upcoming_events)}")

        except Exception as e:
            if not self._te_error_logged:
                logger.warning(f"TradingEconomics error: {e}")
                self._te_error_logged = True
            else:
                logger.debug(f"TradingEconomics error (silenciado): {e}")
            raise

    def _fetch_fallback(self):
        """Fallback: eventos hardcodeados de alta importancia"""
        now = datetime.now()
        today = now.date()

        fallback_events = [
            {"name": "NFP", "country": "United States", "time": "08:30", "days": [4]},
            {"name": "CPI", "country": "United States", "time": "08:30", "days": [0, 1, 2, 3, 4, 5, 6]},
            {"name": "FOMC", "country": "United States", "time": "14:00", "days": [2]},
            {"name": "GDP", "country": "United States", "time": "08:30", "days": [4]},
        ]

        self.upcoming_events = []
        for item in fallback_events:
            if today.weekday() in item["days"]:
                hour, minute = map(int, item["time"].split(":"))
                event_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
                if event_time > now:
                    self.upcoming_events.append({
                        "name": item["name"],
                        "country": item["country"],
                        "date": event_time,
                    })

        logger.info(f"Fallback events: {len(self.upcoming_events)}")

    def _parse_events(self, data) -> list:
        """Parsea eventos del API"""
        events = []

        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except Exception:
                return events

        if not isinstance(data, list):
            return events

        for item in data:
            try:
                date_str = item.get("Date", "")
                if not date_str:
                    continue

                event_time = self._parse_date(date_str)
                if not event_time:
                    continue

                if event_time < datetime.now():
                    continue

                event_name = item.get("Event", "")
                country = item.get("Country", "")
                importance = str(item.get("Importance", ""))

                if self.high_impact_only and importance not in ["3", "High", "high"]:
                    continue

                is_high_impact = any(
                    kw in event_name.upper()
                    for kw in self.HIGH_IMPACT_KEYWORDS
                )

                if self.high_impact_only and not is_high_impact:
                    continue

                events.append({
                    "name": event_name,
                    "country": country,
                    "date": event_time,
                    "importance": importance,
                })

            except Exception as e:
                logger.debug(f"Error parsing event: {e}")
                continue

        return events

    def _parse_date(self, date_str: str):
        """Parsea string de fecha del API"""
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _event_to_symbol(self, event: dict) -> str:
        """Convierte evento a simbolo de trading"""
        country = event.get("country", "").upper()

        mapping = {
            "UNITED STATES": "USD",
            "EURO ZONE": "EUR",
            "GERMANY": "EUR",
            "FRANCE": "EUR",
            "ITALY": "EUR",
            "SPAIN": "EUR",
            "JAPAN": "JPY",
            "UNITED KINGDOM": "GBP",
            "CANADA": "CAD",
            "AUSTRALIA": "AUD",
            "NEW ZEALAND": "NZD",
            "SWITZERLAND": "CHF",
            "CHINA": "CNY",
        }

        currency = mapping.get(country, "")
        if not currency:
            return None

        pairs = {
            "USD": "XAUUSD",
            "EUR": "EURUSD",
            "GBP": "GBPUSD",
            "JPY": "USDJPY",
            "CAD": "USDCAD",
            "AUD": "AUDUSD",
            "NZD": "NZDUSD",
            "CHF": "USDCHF",
        }

        return pairs.get(currency)

    def get_status(self) -> dict:
        """Estado del filtro"""
        return {
            "enabled": self.enabled,
            "minutes_before": self.minutes_before,
            "minutes_after": self.minutes_after,
            "high_impact_only": self.high_impact_only,
            "upcoming_events": len(self.upcoming_events),
            "next_event": self.upcoming_events[0] if self.upcoming_events else None,
        }
