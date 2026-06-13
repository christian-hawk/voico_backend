"""Background tasks for the calls module."""

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.db import async_session
from app.modules.calls.repository import CallRepository

logger = logging.getLogger(__name__)


async def expire_stale_calls_once() -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=settings.stale_expiry_threshold_seconds)
    async with async_session() as session:
        count = await CallRepository(session).expire_stale_calls(cutoff)
        await session.commit()
    logger.info("Expired %d stale call(s)", count)
    return count


async def stale_call_expiry_loop() -> None:
    while True:
        await asyncio.sleep(settings.stale_expiry_interval_seconds)
        try:
            await expire_stale_calls_once()
        except Exception:
            logger.exception("Stale-call expiry run failed")
