import asyncio
import json
from nats.aio.client import Client

async def main():
    nc = Client()
    await nc.connect("nats://localhost:4222")
    msg = json.dumps({"chat_id": 123456789, "text": "TNSVT bot active"})
    await nc.publish("notification.telegram.send", msg.encode())
    await nc.flush()
    await nc.close()
    print("OK - published to NATS")

asyncio.run(main())
