"""用户相关 API 路由（历史行程）"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from ...core.deps import get_current_user
from ...models.db_models import User
from ...models.schemas import TripHistoryDetail, TripHistoryItem
from ...services.trip_history_service import (
    delete_trip,
    get_trip_detail,
    list_user_trips,
)

router = APIRouter(prefix="/user", tags=["用户"])


@router.get("/trips", response_model=List[TripHistoryItem])
async def list_trips(current_user: User = Depends(get_current_user)):
    """获取当前用户的历史行程列表"""
    return await list_user_trips(current_user.id)


@router.get("/trips/{trip_id}", response_model=TripHistoryDetail)
async def get_trip(trip_id: int, current_user: User = Depends(get_current_user)):
    """获取单条历史行程详情"""
    trip = await get_trip_detail(current_user.id, trip_id)
    if not trip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="行程不存在")
    return trip


@router.delete("/trips/{trip_id}")
async def remove_trip(trip_id: int, current_user: User = Depends(get_current_user)):
    """删除一条历史行程"""
    ok = await delete_trip(current_user.id, trip_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="行程不存在")
    return {"success": True, "message": "已删除"}
