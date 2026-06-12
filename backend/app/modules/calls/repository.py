import math
import uuid
from typing import Any, Optional

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.calls.schema import Call, CallLabel, CallStatus

_LIKE_ESCAPE = "\\"
_PHONE_SEPARATORS = "+() -"


def _escape_like(term: str) -> str:
    escaped = term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE + _LIKE_ESCAPE)
    escaped = escaped.replace("%", _LIKE_ESCAPE + "%")
    return escaped.replace("_", _LIKE_ESCAPE + "_")


def _normalized_phone() -> Any:
    expr: Any = col(Call.phone_number)
    for separator in _PHONE_SEPARATORS:
        expr = func.replace(expr, separator, "")
    return expr


class CallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, call_id: uuid.UUID) -> Optional[Call]:
        result = await self.session.exec(select(Call).where(Call.id == call_id))
        return result.first()

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
    ) -> tuple[list[Call], int, int, dict[str, int]]:
        conditions: list[Any] = []
        if status is not None:
            conditions.append(Call.status == status)
        if caller_name is not None:
            pattern = f"%{_escape_like(caller_name)}%"
            conditions.append(col(Call.caller_name).ilike(pattern, escape=_LIKE_ESCAPE))
        if phone_number is not None:
            digits = "".join(char for char in phone_number if char.isdigit())
            if digits:
                # digits-only term: compare digits against digits, ignoring formatting
                conditions.append(_normalized_phone().like(f"%{digits}%"))
            else:
                pattern = f"%{_escape_like(phone_number)}%"
                conditions.append(col(Call.phone_number).ilike(pattern, escape=_LIKE_ESCAPE))
        if label is not None:
            conditions.append(Call.label == label)
        if min_duration is not None:
            conditions.append(col(Call.duration_seconds) >= min_duration)
        if max_duration is not None:
            conditions.append(col(Call.duration_seconds) <= max_duration)

        query = select(Call)
        count_query = select(func.count()).select_from(Call)

        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)

        count_result = await self.session.exec(count_query)
        total = count_result.one()

        counts: dict[str, int] = {}
        for s in CallStatus:
            c = (
                await self.session.exec(
                    select(func.count()).select_from(Call).where(Call.status == s)
                )
            ).one()
            counts[s.value] = c

        offset = (page - 1) * page_size
        query = query.order_by(Call.created_at.desc()).offset(offset).limit(page_size)  # type: ignore[attr-defined]
        result = await self.session.exec(query)
        calls = list(result.all())

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return calls, total, total_pages, counts

    async def update(self, call: Call) -> Call:
        self.session.add(call)
        await self.session.flush()
        await self.session.refresh(call)
        return call
