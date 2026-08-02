"""Entry point for running the regime-detector service standalone."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.main import create_app
from app.services.config import Settings
from app.services.dependencies import Dependencies

cfg = Settings()
deps = Dependencies(cfg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await deps.connect()
    await deps.start_subscriber()
    yield
    await deps.close()


app = create_app(deps)
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="0.0.0.0", port=cfg.port, log_level=cfg.log_level.lower(), reload=False)
