import uuid
from datetime import datetime


async def test_patch_notes_sets_value(client, make_call):
    call = await make_call()

    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "a note"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "a note"
    assert datetime.fromisoformat(body["updated_at"]) > call.updated_at

    persisted = await client.get(f"/api/calls/{call.id}")
    assert persisted.json()["notes"] == "a note"


async def test_patch_notes_null_clears(client, make_call):
    call = await make_call(notes="initial")

    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": None})

    assert resp.status_code == 200
    assert resp.json()["notes"] is None

    persisted = await client.get(f"/api/calls/{call.id}")
    assert persisted.json()["notes"] is None


async def test_patch_notes_empty_body_returns_422(client, make_call):
    call = await make_call()

    resp = await client.patch(f"/api/calls/{call.id}/notes", json={})

    assert resp.status_code == 422


async def test_patch_notes_invalid_uuid_returns_422(client):
    resp = await client.patch("/api/calls/not-a-uuid/notes", json={"notes": "x"})

    assert resp.status_code == 422


async def test_patch_notes_unknown_id_returns_404(client):
    resp = await client.patch(f"/api/calls/{uuid.uuid4()}/notes", json={"notes": "x"})

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Call not found"


async def test_patch_notes_multiline_roundtrip(client, make_call):
    call = await make_call()
    notes = "line 1\nline 2\n\nline 4"

    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": notes})

    assert resp.status_code == 200
    assert resp.json()["notes"] == notes

    persisted = await client.get(f"/api/calls/{call.id}")
    assert persisted.json()["notes"] == notes


async def test_patch_notes_preserves_other_fields(client, make_call):
    call = await make_call(
        caller_name="Jane Doe",
        summary="existing summary",
        raw_transcript="existing transcript",
        duration_seconds=42,
    )

    resp = await client.patch(f"/api/calls/{call.id}/notes", json={"notes": "a note"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["caller_name"] == "Jane Doe"
    assert body["summary"] == "existing summary"
    assert body["raw_transcript"] == "existing transcript"
    assert body["duration_seconds"] == 42
    assert body["status"] == call.status.value


async def test_get_calls_includes_notes(client, make_call):
    with_notes = await make_call(notes="annotated")
    without_notes = await make_call()

    listed = await client.get("/api/calls")

    assert listed.status_code == 200
    by_id = {item["id"]: item for item in listed.json()["data"]}
    assert by_id[str(with_notes.id)]["notes"] == "annotated"
    assert by_id[str(without_notes.id)]["notes"] is None
