"""
Magic number centralizado para el signal_copier.

Por defecto usa 20260706 (legacy). Se puede override via MT5_MAGIC_NUMBER
para que coincida con el magic que usa el execution-engine (que calcula
trading.MagicForAccount(account_id) → 77000xxx).
"""
import os

DEFAULT_MAGIC = 20260706
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", str(DEFAULT_MAGIC)))
