import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.modules.calls.ai import enrich_call
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    Call,
    CallCounts,
    CallLabel,
    CallResponse,
    CallStatus,
    PaginatedCallsResponse,
    SortDir,
    SortField,
    WebhookCallPayload,
)

logger = logging.getLogger(__name__)

# the status param shadows fastapi.status inside list_calls
_HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT


class CallService:
    def __init__(self, repository: CallRepository) -> None:
        self.repository = repository

    async def list_calls(
        self,
        status: Optional[CallStatus],
        page: int,
        page_size: int,
        caller_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        label: Optional[CallLabel] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        sort_by: Optional[SortField] = None,
        sort_dir: SortDir = SortDir.asc,
    ) -> PaginatedCallsResponse:
        if min_duration is not None and max_duration is not None and min_duration > max_duration:
            raise HTTPException(
                status_code=_HTTP_422,
                detail="min_duration cannot exceed max_duration",
            )
        calls, total, total_pages, counts = await self.repository.list_calls(
            status,
            page,
            page_size,
            caller_name=caller_name,
            phone_number=phone_number,
            label=label,
            min_duration=min_duration,
            max_duration=max_duration,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        return PaginatedCallsResponse(
            data=[CallResponse.model_validate(c, from_attributes=True) for c in calls],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            counts=CallCounts(
                in_progress=counts.get("in_progress", 0),
                success=counts.get("success", 0),
                failed=counts.get("failed", 0),
            ),
        )

    async def _get_call_or_404(self, call_id: uuid.UUID) -> Call:
        call = await self.repository.get_by_id(call_id)
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        return call

    async def get_call(self, call_id: uuid.UUID) -> CallResponse:
        call = await self._get_call_or_404(call_id)
        return CallResponse.model_validate(call, from_attributes=True)

    async def update_notes(self, call_id: uuid.UUID, notes: Optional[str]) -> CallResponse:
        call = await self._get_call_or_404(call_id)
        if call.notes != notes:
            call.notes = notes
            call = await self.repository.update(call)
        return CallResponse.model_validate(call, from_attributes=True)

    async def process_webhook(self, payload: WebhookCallPayload) -> CallResponse:
        call = await self._get_call_or_404(payload.call_id)
        call.status = payload.status
        if payload.duration_seconds is not None:
            call.duration_seconds = payload.duration_seconds
        if payload.raw_transcript is not None:
            call.raw_transcript = payload.raw_transcript
        if payload.ended_at is not None:
            call.ended_at = payload.ended_at
        if payload.status in (CallStatus.success, CallStatus.failed) and payload.raw_transcript:
            enrichment = await enrich_call(payload.raw_transcript)
            if enrichment is not None:
                call.summary = enrichment.summary
                call.label = enrichment.label
        call = await self.repository.update(call)
        return CallResponse.model_validate(call, from_attributes=True)
