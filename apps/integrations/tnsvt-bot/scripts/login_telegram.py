"""
Login simplificado - todo en uno
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from config import settings

SESSION = "signal_copier/session"

async def main():
    code = sys.argv[1] if len(sys.argv) > 1 else None
    
    client = TelegramClient(SESSION, settings.TELETHON_API_ID, settings.TELETHON_API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"YA ESTAS LOGUEADO: {me.first_name} (@{me.username})")
        await client.disconnect()
        return
    
    if not code:
        # Enviar código
        result = await client.send_code_request(settings.TELETHON_PHONE)
        # Guardar hash en archivo
        with open("signal_copier/code_hash.txt", "w") as f:
            f.write(result.phone_code_hash)
        print(f"Código enviado a {settings.TELETHON_PHONE}")
        print("Ahora ejecuta: python login_telegram.py CODIGO")
    else:
        # Confirmar código
        try:
            with open("signal_copier/code_hash.txt", "r") as f:
                phone_code_hash = f.read().strip()
            
            await client.sign_in(
                phone=settings.TELETHON_PHONE,
                code=code,
                phone_code_hash=phone_code_hash
            )
            me = await client.get_me()
            print(f"LOGIN EXITOSO: {me.first_name} (@{me.username})")
        except Exception as e:
            print(f"Error: {e}")
    
    await client.disconnect()

asyncio.run(main())
