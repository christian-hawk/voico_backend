import uuid

from app.core.config import settings
from app.modules.calls.ai import CallEnrichment, enrich_call
from app.modules.calls.schema import CallLabel

URL = "/api/webhook/call"


def _payload(call_id, **overrides):
    body = {
        "call_id": str(call_id),
        "status": "success",
        "duration_seconds": 120,
        "ended_at": "2024-01-01T12:00:00",
        "raw_transcript": "Agent: How can I help?\nCaller: I need to upgrade my plan.",
    }
    body.update(overrides)
    return body


def _fake_enrichment(summary="A short summary.", label=CallLabel.support):
    async def _enrich(transcript: str) -> CallEnrichment:
        return CallEnrichment(summary=summary, label=label)

    return _enrich


def _raising_client(*args, **kwargs):
    raise RuntimeError("api down")


async def test_webhook_updates_call_fields(client, make_call, monkeypatch):
    call = await make_call()
    monkeypatch.setattr("app.modules.calls.service.enrich_call", _fake_enrichment())

    resp = await client.post(URL, json=_payload(call.id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["duration_seconds"] == 120
    assert body["raw_transcript"].startswith("Agent:")
    assert body["ended_at"].startswith("2024-01-01T12:00:00")


async def test_webhook_enriches_on_success_with_transcript(client, make_call, monkeypatch):
    call = await make_call()
    monkeypatch.setattr(
        "app.modules.calls.service.enrich_call",
        _fake_enrichment("Caller upgraded.", CallLabel.sales_inquiry),
    )

    resp = await client.post(URL, json=_payload(call.id, status="success"))

    body = resp.json()
    assert body["summary"] == "Caller upgraded."
    assert body["label"] == "Sales inquiry"


async def test_webhook_enriches_on_failed_with_transcript(client, make_call, monkeypatch):
    call = await make_call()
    monkeypatch.setattr(
        "app.modules.calls.service.enrich_call",
        _fake_enrichment("Issue unresolved.", CallLabel.complaint),
    )

    resp = await client.post(URL, json=_payload(call.id, status="failed"))

    body = resp.json()
    assert body["status"] == "failed"
    assert body["summary"] == "Issue unresolved."
    assert body["label"] == "Complaint"


async def test_webhook_skips_enrichment_without_transcript(client, make_call, monkeypatch):
    call = await make_call()
    called = False

    async def _enrich(transcript: str) -> CallEnrichment:
        nonlocal called
        called = True
        return CallEnrichment(summary="x", label=CallLabel.other)

    monkeypatch.setattr("app.modules.calls.service.enrich_call", _enrich)

    resp = await client.post(URL, json=_payload(call.id, status="success", raw_transcript=None))

    body = resp.json()
    assert called is False
    assert body["summary"] is None
    assert body["label"] is None


async def test_webhook_skips_enrichment_when_in_progress(client, make_call, monkeypatch):
    call = await make_call()
    called = False

    async def _enrich(transcript: str) -> CallEnrichment:
        nonlocal called
        called = True
        return CallEnrichment(summary="x", label=CallLabel.other)

    monkeypatch.setattr("app.modules.calls.service.enrich_call", _enrich)

    resp = await client.post(URL, json=_payload(call.id, status="in_progress"))

    assert called is False
    assert resp.json()["summary"] is None


async def test_webhook_persists_on_openai_failure(client, make_call, monkeypatch):
    call = await make_call()

    async def _enrich(transcript: str):
        return None

    monkeypatch.setattr("app.modules.calls.service.enrich_call", _enrich)

    resp = await client.post(URL, json=_payload(call.id, status="success"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["raw_transcript"].startswith("Agent:")
    assert body["summary"] is None
    assert body["label"] is None


async def test_webhook_persists_when_client_raises(client, make_call, monkeypatch):
    call = await make_call()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr("app.modules.calls.ai.AsyncOpenAI", _raising_client)

    resp = await client.post(URL, json=_payload(call.id, status="success"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["summary"] is None
    assert body["label"] is None


async def test_webhook_unknown_call_returns_404(client, monkeypatch):
    monkeypatch.setattr("app.modules.calls.service.enrich_call", _fake_enrichment())

    resp = await client.post(URL, json=_payload(uuid.uuid4()))

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Call not found"


async def test_enrich_call_returns_none_on_client_error(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr("app.modules.calls.ai.AsyncOpenAI", _raising_client)

    result = await enrich_call("Agent: hi\nCaller: bye")

    assert result is None
