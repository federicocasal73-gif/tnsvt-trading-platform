"""
Autenticación del bot contra el bridge-api.

El bridge-api valida las llamadas de servicios internos mediante el header
X-Admin-Password (configurado en .env como BRIDGE_ADMIN_PASSWORD en el bridge
y TNSVT_ADMIN_PASSWORD en el bot). El bot NO usa JWT: es un servicio interno.
"""
from config import settings


def bridge_headers() -> dict:
    h = {"Content-Type": "application/json"}
    pwd = settings.TNSVT_ADMIN_PASSWORD
    if pwd:
        h["X-Admin-Password"] = pwd
    return h
