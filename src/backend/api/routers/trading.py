from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import get_current_user, get_database
from ..models.base import BaseOrder, OrderStatus, Position

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/orders", response_model=BaseOrder)
async def create_order(
    order: BaseOrder,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    order_dict = order.model_dump()
    order_dict["user_id"] = current_user["id"]
    result = await db.orders.insert_one(order_dict)
    order_dict["id"] = str(result.inserted_id)
    return order_dict


@router.get("/orders", response_model=List[BaseOrder])
async def get_orders(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    orders = await db.orders.find({"user_id": current_user["id"]}).to_list(None)
    return orders


@router.get("/orders/{order_id}", response_model=BaseOrder)
async def get_order(
    order_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    order = await db.orders.find_one({"_id": order_id, "user_id": current_user["id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    result = await db.orders.update_one(
        {"_id": order_id, "user_id": current_user["id"]},
        {"$set": {"status": OrderStatus.CANCELLED, "updated_at": datetime.utcnow()}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "success"}


@router.get("/positions", response_model=List[Position])
async def get_positions(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    positions = await db.positions.find({"user_id": current_user["id"]}).to_list(None)
    return positions


@router.get("/positions/{symbol}", response_model=Position)
async def get_position(
    symbol: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    position = await db.positions.find_one(
        {"symbol": symbol, "user_id": current_user["id"]}
    )
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position
