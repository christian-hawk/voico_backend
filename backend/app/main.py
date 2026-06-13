import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.calls.router import router as calls_router
from app.modules.calls.tasks import stale_call_expiry_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set; call enrichment is disabled")
    task = asyncio.create_task(stale_call_expiry_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title=settings.app_name,
    description="Backend API for the Voico Calls Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calls_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": settings.app_name}
