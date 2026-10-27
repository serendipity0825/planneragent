"""历史行程服务（每个方法自管会话，避免 SSE 生成器管理会话生命周期）"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import AsyncSessionLocal
from ..models.db_models import TripHistory
from ..models.schemas import TripRequest


def _build_title(request: TripRequest, itinerary: dict) -> str:
    city = itinerary.get("city") or request.city
    start = itinerary.get("start_date") or request.start_date
    if start:
        return f"{city} · {start}（{request.travel_days}天）"
    return f"{city}（{request.travel_days}天）"


async def save_trip_history(
    user_id: int, session_id: str, request: TripRequest, itinerary: dict
) -> TripHistory:
    """保存/更新历史行程（按 user_id + session_id upsert）"""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(TripHistory).where(
                TripHistory.user_id == user_id,
                TripHistory.session_id == session_id,
            )
        )
        trip = existing.scalar_one_or_none()

        payload = {
            "title": _build_title(request, itinerary),
            "city": itinerary.get("city") or request.city,
            "start_date": itinerary.get("start_date") or request.start_date,
            "end_date": itinerary.get("end_date") or request.end_date,
            "travel_days": request.travel_days,
            "transportation": request.transportation,
            "accommodation": request.accommodation,
            "preferences": request.preferences or [],
            "free_text_input": request.free_text_input or "",
            "budget": request.budget or [],
            "result": itinerary,
        }

        if trip is None:
            trip = TripHistory(user_id=user_id, session_id=session_id, **payload)
            db.add(trip)
        else:
            for key, value in payload.items():
                setattr(trip, key, value)

        await db.commit()
        await db.refresh(trip)
        return trip


async def list_user_trips(user_id: int) -> list[TripHistory]:
    """列出用户所有历史行程（按创建时间倒序）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TripHistory)
            .where(TripHistory.user_id == user_id)
            .order_by(TripHistory.created_at.desc())
        )
        return list(result.scalars().all())


async def get_trip_detail(user_id: int, trip_id: int):
    """获取单条历史行程（含归属校验，他人行程返回 None）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TripHistory).where(
                TripHistory.id == trip_id,
                TripHistory.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def delete_trip(user_id: int, trip_id: int) -> bool:
    """删除历史行程，返回是否删除成功"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TripHistory).where(
                TripHistory.id == trip_id,
                TripHistory.user_id == user_id,
            )
        )
        trip = result.scalar_one_or_none()
        if trip is None:
            return False
        await db.delete(trip)
        await db.commit()
        return True
