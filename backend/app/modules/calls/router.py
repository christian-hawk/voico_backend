import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_session
from app.core.decorators import session_manager
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    CallLabel,
    CallResponse,
    CallStatus,
    PaginatedCallsResponse,
    SortDir,
    SortField,
    UpdateNotesRequest,
    WebhookCallPayload,
)
from app.modules.calls.service import CallService

router = APIRouter()


async def get_session():
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_call_service(session: SessionDep) -> CallService:
    return CallService(CallRepository(session))


@router.get("/calls", response_model=PaginatedCallsResponse)
async def list_calls(
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
    status: Optional[CallStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    caller_name: Optional[str] = Query(
        default=None,
        min_length=1,
        description="Partial match on caller name (ASCII case-insensitive)",
    ),
    phone_number: Optional[str] = Query(
        default=None,
        min_length=1,
        description="Partial match on phone number; digits match digits regardless of formatting",
    ),
    label: Optional[CallLabel] = Query(default=None, description="Exact label match"),
    min_duration: Optional[int] = Query(
        default=None, ge=0, description="Minimum duration in seconds, inclusive"
    ),
    max_duration: Optional[int] = Query(
        default=None, ge=0, description="Maximum duration in seconds, inclusive"
    ),
    sort_by: Optional[SortField] = Query(
        default=None, description="Column to sort by; omitted keeps newest-first ordering"
    ),
    sort_dir: SortDir = Query(
        default=SortDir.asc, description="Sort direction; only applies with sort_by"
    ),
) -> PaginatedCallsResponse:
    return await service.list_calls(
        status=status,
        page=page,
        page_size=page_size,
        caller_name=caller_name,
        phone_number=phone_number,
        label=label,
        min_duration=min_duration,
        max_duration=max_duration,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/calls/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    return await service.get_call(call_id)


@router.patch("/calls/{call_id}/notes", response_model=CallResponse)
@session_manager
async def update_call_notes(
    call_id: uuid.UUID,
    payload: UpdateNotesRequest,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    return await service.update_notes(call_id, payload.notes)


@router.post("/webhook/call", response_model=CallResponse)
@session_manager
async def webhook_call(
    payload: WebhookCallPayload,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    return await service.process_webhook(payload)
