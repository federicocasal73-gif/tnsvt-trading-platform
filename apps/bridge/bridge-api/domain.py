"""
Domain models compartidos entre bridge y (futuro) signal_copier.

ChannelProfile — replica el formato que usa TFP `signal_copier/channel_profile.py`
para describir un canal Telegram y sus topics de foro. Sirve como contrato
entre el bot (que escanea Telegram), el bridge (que persiste/expone) y la UI
React (que muestra y edita selección).
"""

from typing import Optional
from pydantic import BaseModel, Field


class Topic(BaseModel):
    id: int
    title: str


class ChannelProfile(BaseModel):
    """Un canal Telegram detectado y sus tópicos (si es foro)."""
    name: str
    id: int
    is_forum: bool = False
    topics: list[Topic] = Field(default_factory=list)


class ChannelProfile(BaseModel):
    """Per-channel trading rules (Phase 2).

    default_symbol:    si la señal llega sin símbolo (raro), usar este.
    allow_symbols:     whitelist. Si está vacío, se acepta todo (sujeto a block).
    block_symbols:     blacklist. Siempre se rechazan (prevalecen sobre allow).
    multi_same_symbol: si False, no abre 2da posición del mismo símbolo.
    max_positions:     tope de posiciones abiertas para ESTE canal.
                       0 = ilimitado.
    max_spread_pips:   spread máximo permitido al abrir. 0 = sin límite.
    """
    default_symbol: Optional[str] = None
    allow_symbols: list[str] = Field(default_factory=list)
    block_symbols: list[str] = Field(default_factory=list)
    multi_same_symbol: bool = True
    max_positions: int = 0
    max_spread_pips: int = 0


class ChannelSelection(BaseModel):
    """Una selección persistible: canal + topic opcional + su Profile."""
    id: int
    name: str
    topic_id: Optional[int] = None
    profile: ChannelProfile = Field(default_factory=ChannelProfile)


class ScanRequest(BaseModel):
    action: str = Field(default="scan_channels")
    request_id: Optional[str] = None


class ScanResponse(BaseModel):
    status: str  # "OK" | "ERROR" | "NO_SCAN" | "PENDING"
    request_id: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    data: list[ChannelProfile] = Field(default_factory=list)


class TenantContext(BaseModel):
    """Contexto multi-tenant propagado en headers y payloads."""
    tenant_id: str = "default"
    source: str = "mt5-bot"
