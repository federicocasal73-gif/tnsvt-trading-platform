"""
Terminal Financiera Pro - Configuración Centralizada
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

ROOT_DIR = Path(__file__).parent.parent
ENV_PATH = ROOT_DIR / ".env"


def load_env():
    """Carga variables desde .env"""
    load_dotenv(ENV_PATH, override=True)


load_env()


class Settings:
    """Configuración centralizada del sistema"""

    def __init__(self):
        pass

    # ============================================
    # TELEGRAM BOT
    # ============================================
    @property
    def BOT_TOKEN(self) -> str:
        return os.getenv("BOT_TOKEN", "")

    @property
    def BOT_ADMIN_IDS(self) -> list:
        """Lista de Telegram user IDs con acceso admin. Vacía = sin restricción."""
        raw = os.getenv("BOT_ADMIN_IDS", "")
        if not raw.strip():
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]

    # ============================================
    # TRADING ECONOMICS
    # ============================================
    @property
    def TE_USERNAME(self) -> str:
        return os.getenv("TRADING_USERNAME", "")

    @property
    def TE_PASSWORD(self) -> str:
        return os.getenv("TRADING_PASSWORD", "")

    # ============================================
    # JBLANKED API
    # ============================================
    @property
    def JBLANKED_API_KEY(self) -> str:
        return os.getenv("JBLANKED_API_KEY", "")

    # ============================================
    # NEWS API
    # ============================================
    @property
    def NEWSAPI_KEY(self) -> str:
        return os.getenv("NEWSAPI_KEY", "")

    # ============================================
    # SIGNAL COPIER - TELETHON
    # ============================================
    @property
    def TELETHON_API_ID(self) -> int:
        return int(os.getenv("TELETHON_API_ID", "0"))

    @property
    def TELETHON_API_HASH(self) -> str:
        return os.getenv("TELETHON_API_HASH", "")

    @property
    def TELETHON_PHONE(self) -> str:
        return os.getenv("TELETHON_PHONE", "")

    # ============================================
    # CANALES
    # ============================================
    @property
    def CHANNELS_CONFIG(self) -> dict:
        """Retorna {canal: habilitado} desde CHANNELS=Canal1=true,Canal2=false"""
        raw = os.getenv("CHANNELS", "")
        channels = {}
        for item in raw.split(","):
            item = item.strip()
            if "=" in item:
                name, enabled = item.split("=", 1)
                channels[name.strip()] = enabled.strip().lower() == "true"
        return channels

    @property
    def CHANNELS_TO_MONITOR(self) -> list:
        """Solo canales habilitados"""
        return [name for name, enabled in self.CHANNELS_CONFIG.items() if enabled]

    # ============================================
    # SIGNAL COPIER - MT5
    # ============================================
    @property
    def SYMBOL_SUFFIX(self) -> str:
        return os.getenv("SYMBOL_SUFFIX", "")

    @property
    def LOT_SIZE(self) -> float:
        return float(os.getenv("LOT_SIZE", "0.01"))

    @property
    def LOT_MODE(self) -> str:
        """fixed o percent"""
        return os.getenv("LOT_MODE", "fixed").lower()

    @property
    def LOT_RISK_PERCENT(self) -> float:
        """Porcentaje del balance por trade"""
        return float(os.getenv("LOT_RISK_PERCENT", "1.0"))

    @property
    def DEVIATION(self) -> int:
        return int(os.getenv("DEVIATION", "20"))

    # ============================================
    # RISK MANAGEMENT
    # ============================================
    @property
    def RISK_DAILY_LOSS_LIMIT(self) -> float:
        return float(os.getenv("RISK_DAILY_LOSS_LIMIT", "2.0"))

    @property
    def RISK_DAILY_PROFIT_TARGET(self) -> float:
        return float(os.getenv("RISK_DAILY_PROFIT_TARGET", "5.0"))

    @property
    def RISK_WEEKLY_LOSS_LIMIT(self) -> float:
        return float(os.getenv("RISK_WEEKLY_LOSS_LIMIT", "5.0"))

    @property
    def RISK_MAX_OPEN_POSITIONS(self) -> int:
        return int(os.getenv("RISK_MAX_OPEN_POSITIONS", "5"))

    @property
    def RISK_TRAILING_STOP(self) -> bool:
        return os.getenv("RISK_TRAILING_STOP", "false").lower() == "true"

    @property
    def RISK_TRAILING_STEP(self) -> float:
        return float(os.getenv("RISK_TRAILING_STEP", "10"))

    @property
    def RISK_TRAILING_START(self) -> float:
        return float(os.getenv("RISK_TRAILING_START", "50"))

    # ============================================
    # NEWS FILTER
    # ============================================
    @property
    def NEWS_FILTER_ENABLED(self) -> bool:
        return os.getenv("NEWS_FILTER_ENABLED", "true").lower() == "true"

    @property
    def NEWS_FILTER_MINUTES_BEFORE(self) -> int:
        return int(os.getenv("NEWS_FILTER_MINUTES_BEFORE", "15"))

    @property
    def NEWS_FILTER_MINUTES_AFTER(self) -> int:
        return int(os.getenv("NEWS_FILTER_MINUTES_AFTER", "15"))

    @property
    def NEWS_FILTER_HIGH_IMPACT_ONLY(self) -> bool:
        return os.getenv("NEWS_FILTER_HIGH_IMPACT_ONLY", "true").lower() == "true"

    # ============================================
    # DASHBOARD
    # ============================================
    @property
    def DASHBOARD_PORT(self) -> int:
        return int(os.getenv("DASHBOARD_PORT", "8501"))

    # ============================================
    # RELOAD
    # ============================================
    def reload(self):
        """Recarga todas las variables desde .env"""
        load_env()

    # ============================================
    # SAVE
    # ============================================
    def validate_trading(self) -> list:
        """Valida configuracion de trading y retorna warnings."""
        warnings = []

        if not self.TE_USERNAME or not self.TE_PASSWORD:
            warnings.append("TRADING_USERNAME/PASSWORD no configurados (Trading Economics deshabilitado)")

        if not self.JBLANKED_API_KEY:
            warnings.append("JBLANKED_API_KEY no configurado (mercado cripto deshabilitado)")

        if not self.NEWSAPI_KEY:
            warnings.append("NEWSAPI_KEY no configurado (noticias deshabilitadas)")

        if not self.TELETHON_API_ID or not self.TELETHON_API_HASH:
            warnings.append("TELETHON_API_ID/HASH no configurados (signal copier deshabilitado)")

        if not self.BOT_TOKEN:
            warnings.append("BOT_TOKEN no configurado (bot de Telegram deshabilitado)")

        if self.RISK_DAILY_LOSS_LIMIT <= 0 or self.RISK_DAILY_LOSS_LIMIT > 10:
            warnings.append(f"RISK_DAILY_LOSS_LIMIT={self.RISK_DAILY_LOSS_LIMIT}% fuera de rango seguro (0-10%)")

        if self.RISK_MAX_OPEN_POSITIONS < 1 or self.RISK_MAX_OPEN_POSITIONS > 50:
            warnings.append(f"RISK_MAX_OPEN_POSITIONS={self.RISK_MAX_OPEN_POSITIONS} fuera de rango (1-50)")

        return warnings

    # ============================================
    # SAVE
    # ============================================
    def save(self, updates: dict):
        """Guarda actualizaciones en .env (escritura atómica)"""
        current = dotenv_values(ENV_PATH)
        current.update(updates)

        lines = []
        for key, value in current.items():
            if value is not None:
                lines.append(f"{key}={value}")

        temp_path = str(ENV_PATH) + ".tmp"
        Path(temp_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temp_path, str(ENV_PATH))
        self.reload()

    # ============================================
    # UTILS
    # ============================================
    def to_dict(self) -> dict:
        """Retorna configuración como diccionario (sin secretos)"""
        return {
            "channels": self.CHANNELS_CONFIG,
            "symbol_suffix": self.SYMBOL_SUFFIX,
            "lot_size": self.LOT_SIZE,
            "lot_mode": self.LOT_MODE,
            "lot_risk_percent": self.LOT_RISK_PERCENT,
            "deviation": self.DEVIATION,
            "risk_daily_loss": self.RISK_DAILY_LOSS_LIMIT,
            "risk_daily_profit": self.RISK_DAILY_PROFIT_TARGET,
            "risk_weekly_loss": self.RISK_WEEKLY_LOSS_LIMIT,
            "risk_max_positions": self.RISK_MAX_OPEN_POSITIONS,
            "trailing_stop": self.RISK_TRAILING_STOP,
            "trailing_step": self.RISK_TRAILING_STEP,
            "trailing_start": self.RISK_TRAILING_START,
            "news_filter_enabled": self.NEWS_FILTER_ENABLED,
            "news_filter_before": self.NEWS_FILTER_MINUTES_BEFORE,
            "news_filter_after": self.NEWS_FILTER_MINUTES_AFTER,
            "news_filter_high_only": self.NEWS_FILTER_HIGH_IMPACT_ONLY,
        }


settings = Settings()
