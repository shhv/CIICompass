from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from .api.admin import start_ingest
from .config import get_settings

logger = logging.getLogger(__name__)


def _seconds_until(hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _daily_reindex_loop(hour: int) -> None:
    while True:
        delay = _seconds_until(hour)
        logger.info("daily reindex scheduled in %.0fs (target hour=%02d:00 local)", delay, hour)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        try:
            started = await start_ingest(force=False)
            logger.info("daily reindex %s", "started" if started else "skipped (already running)")
        except Exception:
            logger.exception("daily reindex trigger failed")
        # Guard against drift if start_ingest returned immediately.
        await asyncio.sleep(60)


async def start_scheduler() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.reindex_enabled:
        logger.info("reindex scheduler disabled")
        return None
    hour = max(0, min(23, settings.reindex_hour))
    if settings.reindex_on_startup:
        try:
            await start_ingest(force=False)
            logger.info("startup reindex triggered")
        except Exception:
            logger.exception("startup reindex failed")
    return asyncio.create_task(_daily_reindex_loop(hour))
