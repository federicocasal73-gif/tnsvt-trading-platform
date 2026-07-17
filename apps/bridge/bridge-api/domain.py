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


class ChannelSelection(BaseModel):
    """Una selección persistible: canal + topic opcional."""
    id: int
    name: str
    topic_id: Optional[int] = None


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
