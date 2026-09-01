from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import ScrapeRun
from .scraper import scrape

_active_refresh: asyncio.Task | None = None
EASTERN = ZoneInfo("America/New_York")


def refresh_dates(start: date | None = None) -> list[date]:
    settings = get_settings()
    first = start or datetime.now(EASTERN).date()
    return [first + timedelta(days=offset) for offset in range(settings.menu_future_days)]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _latest_run() -> ScrapeRun | None:
    async with SessionLocal() as db:
        return await db.scalar(
            select(ScrapeRun)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )


async def menu_cache_is_fresh(dates: list[date]) -> bool:
    latest = await _latest_run()
    if latest is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(1, get_settings().menu_refresh_minutes)
    )
    latest_event = _as_utc(latest.completed_at or latest.started_at)
    if latest.status in {"failed", "running"}:
        return bool(latest_event and latest_event >= cutoff)
    if latest.completed_at is None:
        return False
    requested = set(latest.dates_requested or [])
    if not {value.isoformat() for value in dates}.issubset(requested):
        return False
    return (_as_utc(latest.completed_at) or cutoff) >= cutoff


async def _run_refresh(dates: list[date]) -> None:
    global _active_refresh
    try:
        await scrape(dates)
    except Exception:
        # The scraper writes a failed ScrapeRun with details for the status endpoint.
        pass
    finally:
        _active_refresh = None


async def schedule_menu_refresh(*, force: bool = False) -> bool:
    global _active_refresh
    if _active_refresh is not None and not _active_refresh.done():
        return False
    dates = refresh_dates()
    if not force and await menu_cache_is_fresh(dates):
        return False
    _active_refresh = asyncio.create_task(_run_refresh(dates), name="testfoodo-menu-refresh")
    return True


async def refresh_status() -> tuple[str, datetime | None]:
    if _active_refresh is not None and not _active_refresh.done():
        return "refreshing", None
    latest = await _latest_run()
    if latest is None:
        return "never_run", None
    return latest.status, _as_utc(latest.completed_at)


async def run_menu_refresh_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    while not stop.is_set():
        try:
            await schedule_menu_refresh()
        except Exception:
            # ScrapeRun records detailed failures; keep the API alive and retry later.
            pass
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=max(1, settings.menu_refresh_minutes) * 60
            )
        except TimeoutError:
            continue


async def stop_menu_refresh() -> None:
    global _active_refresh
    if _active_refresh is None or _active_refresh.done():
        return
    _active_refresh.cancel()
    with suppress(asyncio.CancelledError):
        await _active_refresh
    _active_refresh = None
