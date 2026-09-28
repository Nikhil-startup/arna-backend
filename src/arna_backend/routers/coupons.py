from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from arna_backend.database import supabase
from arna_backend.schemas import CouponValidateRequest, CouponValidateResponse

router = APIRouter(prefix="/api/coupons", tags=["Discounts & Coupons"])

class CouponCreate(BaseModel):
    code: str
    type: str # 'percentage' or 'flat'
    value: float
    minOrderValue: Optional[float] = 0
    isActive: Optional[bool] = True

@router.get("")
async def get_coupons():
    """
    Get all active discount promo codes.
    """
    res = supabase.from_("coupons").select("*").order("code").execute()
    return res.data or []

@router.post("/validate", response_model=CouponValidateResponse)
async def validate_coupon(payload: CouponValidateRequest):
    """
    Validate a discount code against the current cart order value.
    """
    clean_code = payload.code.strip().upper()
    res = supabase.from_("coupons").select("*").eq("code", clean_code).maybe_single().execute()
    
    if not res.data:
        return CouponValidateResponse(
            valid=False,
            discount=0,
            code=clean_code,
            message=f"Promo code '{clean_code}' is not valid"
        )

    coupon = res.data
    if not coupon.get("is_active", True):
        return CouponValidateResponse(
            valid=False,
            discount=0,
            code=clean_code,
            message=f"Promo code '{clean_code}' has expired or is inactive"
        )

    min_val = float(coupon.get("min_order_value", 0))
    if payload.orderTotal < min_val:
        return CouponValidateResponse(
            valid=False,
            discount=0,
            code=clean_code,
            message=f"Requires a minimum order value of ₹{int(min_val)}"
        )

    if coupon.get("type") == "percentage":
        discount = round((payload.orderTotal * float(coupon.get("value", 0))) / 100)
    else:
        discount = float(coupon.get("value", 0))

    return CouponValidateResponse(
        valid=True,
        discount=discount,
        code=clean_code,
        message=f"Coupon '{clean_code}' applied! You saved ₹{int(discount)}"
    )

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_coupon(payload: CouponCreate):
    """
    Create a new coupon code (Merchant Admin).
    """
    import time
    coupon_id = f"c_{int(time.time() * 1000)}"
    row = {
        "id": coupon_id,
        "code": payload.code.strip().upper(),
        "type": payload.type,
        "value": payload.value,
        "min_order_value": payload.minOrderValue or 0,
        "is_active": payload.isActive,
        "usage_count": 0
    }
    supabase.from_("coupons").insert(row).execute()
    return {"success": True, "coupon": row}

@router.patch("/{coupon_id}/toggle")
async def toggle_coupon(coupon_id: str, is_active: bool):
    """
    Toggle coupon activation state.
    """
    supabase.from_("coupons").update({"is_active": is_active}).eq("id", coupon_id).execute()
    return {"success": True, "message": f"Coupon {coupon_id} status updated to {is_active}"}
