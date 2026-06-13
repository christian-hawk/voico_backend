import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import CallStatus
from app.modules.calls.tasks import expire_stale_calls_once

THRESHOLD = timedelta(minutes=30)


async def _expire(test_session_factory, cutoff: datetime) -> int:
    async with test_session_factory() as session:
        count = await CallRepository(session).expire_stale_calls(cutoff)
        await session.commit()
    return count


async def _get(test_session_factory, call_id):
    async with test_session_factory() as session:
        return await CallRepository(session).get_by_id(call_id)


async def test_expires_call_older_than_threshold(test_session_factory, make_call):
    now = datetime.utcnow()
    call = await make_call(
        status=CallStatus.in_progress, started_at=now - THRESHOLD - timedelta(minutes=1)
    )

    count = await _expire(test_session_factory, now - THRESHOLD)

    assert count == 1
    assert (await _get(test_session_factory, call.id)).status == CallStatus.failed


async def test_keeps_call_within_threshold(test_session_factory, make_call):
    now = datetime.utcnow()
    call = await make_call(status=CallStatus.in_progress, started_at=now - timedelta(minutes=10))

    count = await _expire(test_session_factory, now - THRESHOLD)

    assert count == 0
    assert (await _get(test_session_factory, call.id)).status == CallStatus.in_progress


async def test_keeps_call_exactly_at_threshold(test_session_factory, make_call):
    now = datetime.utcnow()
    cutoff = now - THRESHOLD
    call = await make_call(status=CallStatus.in_progress, started_at=cutoff)

    count = await _expire(test_session_factory, cutoff)

    assert count == 0
    assert (await _get(test_session_factory, call.id)).status == CallStatus.in_progress


async def test_ignores_non_in_progress(test_session_factory, make_call):
    now = datetime.utcnow()
    old = now - THRESHOLD - timedelta(minutes=1)
    await make_call(status=CallStatus.success, started_at=old)
    await make_call(status=CallStatus.failed, started_at=old)

    count = await _expire(test_session_factory, now - THRESHOLD)

    assert count == 0


async def test_batch_expires_multiple(test_session_factory, make_call):
    now = datetime.utcnow()
    old = now - THRESHOLD - timedelta(minutes=1)
    for _ in range(3):
        await make_call(status=CallStatus.in_progress, started_at=old)

    count = await _expire(test_session_factory, now - THRESHOLD)

    assert count == 3


async def test_no_stale_returns_zero(test_session_factory, make_call):
    now = datetime.utcnow()
    await make_call(status=CallStatus.in_progress, started_at=now - timedelta(minutes=1))

    count = await _expire(test_session_factory, now - THRESHOLD)

    assert count == 0


async def test_updated_at_bumped_on_expiry(test_session_factory, make_call):
    now = datetime.utcnow()
    old = now - THRESHOLD - timedelta(minutes=1)
    call = await make_call(status=CallStatus.in_progress, started_at=old, updated_at=old)

    await _expire(test_session_factory, now - THRESHOLD)

    refreshed = await _get(test_session_factory, call.id)
    assert refreshed.updated_at > old
    assert refreshed.started_at == old


async def test_expiry_sets_ended_at(test_session_factory, make_call):
    now = datetime.utcnow()
    call = await make_call(
        status=CallStatus.in_progress, started_at=now - THRESHOLD - timedelta(minutes=1)
    )

    await _expire(test_session_factory, now - THRESHOLD)

    refreshed = await _get(test_session_factory, call.id)
    assert refreshed.ended_at is not None
    assert refreshed.duration_seconds is None


async def test_once_commits_and_logs(test_session_factory, make_call, monkeypatch, caplog):
    now = datetime.utcnow()
    call = await make_call(
        status=CallStatus.in_progress, started_at=now - THRESHOLD - timedelta(minutes=1)
    )
    monkeypatch.setattr("app.modules.calls.tasks.async_session", test_session_factory)

    with caplog.at_level(logging.INFO, logger="app.modules.calls.tasks"):
        count = await expire_stale_calls_once()

    assert count == 1
    assert "Expired 1 stale call(s)" in caplog.text
    assert (await _get(test_session_factory, call.id)).status == CallStatus.failed


async def test_threshold_is_configurable(test_session_factory, make_call, monkeypatch):
    now = datetime.utcnow()
    # 10 minutes old: kept under the default 30-min threshold, expired under 60 seconds
    await make_call(status=CallStatus.in_progress, started_at=now - timedelta(minutes=10))
    monkeypatch.setattr("app.modules.calls.tasks.async_session", test_session_factory)
    monkeypatch.setattr(settings, "stale_expiry_threshold_seconds", 60)

    count = await expire_stale_calls_once()

    assert count == 1
