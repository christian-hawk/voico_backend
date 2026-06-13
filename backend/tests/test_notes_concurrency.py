from app.modules.calls.ai import enrich_call
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import CallStatus
from app.modules.calls.service import CallService


async def test_update_notes_preserves_concurrent_writes(test_session_factory, make_call):
    call = await make_call()

    async with test_session_factory() as session_a:
        repo_a = CallRepository(session_a)
        service_a = CallService(repo_a, enrich_call)

        # pin the pre-concurrency snapshot in session A's identity map
        stale = await repo_a.get_by_id(call.id)
        assert stale is not None
        assert stale.status == CallStatus.in_progress

        # a concurrent writer (Task 4's webhook) commits in between
        async with test_session_factory() as session_b:
            repo_b = CallRepository(session_b)
            concurrent = await repo_b.get_by_id(call.id)
            concurrent.status = CallStatus.success
            concurrent.summary = "webhook summary"
            await repo_b.update(concurrent)
            await session_b.commit()

        response = await service_a.update_notes(call.id, "a note")
        await session_a.commit()

    assert response.notes == "a note"

    # A's flush writes only the dirty columns (notes, updated_at),
    # so B's committed changes survive
    async with test_session_factory() as session_c:
        final = await CallRepository(session_c).get_by_id(call.id)
        assert final is not None
        assert final.status == CallStatus.success
        assert final.summary == "webhook summary"
        assert final.notes == "a note"
