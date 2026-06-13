"""OpenAI enrichment for the calls module."""

import logging
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.modules.calls.schema import CallLabel

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_SYSTEM = (
    "You summarize a customer support call transcript in 2-3 sentences and "
    "classify it into exactly one of the given labels."
)


class CallEnrichment(BaseModel):
    summary: str
    label: CallLabel


Enricher = Callable[[str], Awaitable[CallEnrichment | None]]


async def enrich_call(transcript: str) -> CallEnrichment | None:
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set; skipping enrichment")
        return None
    try:
        async with AsyncOpenAI(api_key=settings.openai_api_key) as client:
            response = await client.chat.completions.parse(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                response_format=CallEnrichment,
            )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            logger.warning("OpenAI returned no parsed enrichment")
        return parsed
    except Exception:
        logger.exception("OpenAI enrichment failed")
        return None
