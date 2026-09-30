from fastapi import APIRouter, HTTPException, Query, status
import random
import time
from typing import List, Optional
from arna_backend.database import supabase
from arna_backend.schemas import OrderCreate, OrderStatusUpdate

router = APIRouter(prefix="/api/orders", tags=["Orders & Fulfillment"])

import uuid
import re

@router.post("", status_code=status.HTTP_201_CREATED)
async def place_order(payload: OrderCreate, user_id: Optional[str] = Query(None)):
    """
    Place a new customer order:
    1. Idempotency check: returns existing order on duplicate submit.
    2. Validates or creates customer record in public.users.
    3. Generates cryptographic verification key and records order.
    4. Decrements product inventory and tracks 5-hour sold_out_at rule.
    """
    # 1. Idempotency protection against duplicate network submissions
    if payload.idempotencyKey:
        try:
            existing = supabase.from_("orders").select("*").eq("idempotency_key", payload.idempotencyKey).maybe_single().execute()
            if existing.data:
                return {
                    "success": True,
                    "orderId": existing.data["id"],
                    "orderNumber": existing.data["order_number"],
                    "orderVerificationKey": existing.data.get("order_verification_key"),
                    "status": existing.data["status"],
                    "total": existing.data["total_amount"],
                    "customer": existing.data["customer_name"],
                    "message": "Order already processed (idempotent response)"
                }
        except Exception:
            pass

    order_id = f"ord_{int(time.time() * 1000)}"
    order_number = f"ARNA-{random.randint(100000, 999999)}"
    verification_key = payload.orderVerificationKey or f"ARNA-VK-{uuid.uuid4().hex[:6].upper()}-{int(time.time())}"

    # Foreign key satisfaction: Ensure user_id exists in public.users
    valid_user_id = user_id
    if valid_user_id:
        user_check = supabase.from_("users").select("id").eq("id", valid_user_id).maybe_single().execute()
        if not user_check.data:
            supabase.from_("users").insert({
                "id": valid_user_id,
                "name": payload.shippingAddress.name,
                "email": f"{valid_user_id}@customer.arna.co.in",
                "phone": payload.shippingAddress.phone,
                "role": "customer"
            }).execute()
    else:
        guest_id = f"usr_guest_{int(time.time() * 1000)}"
        supabase.from_("users").insert({
            "id": guest_id,
            "name": payload.shippingAddress.name,
            "email": f"{payload.shippingAddress.phone.replace(' ', '')}@guest.arna.co.in",
            "phone": payload.shippingAddress.phone,
            "role": "customer"
        }).execute()
        valid_user_id = guest_id

    # Insert order into public.orders
    order_row = {
        "id": order_id,
        "order_number": order_number,
        "user_id": valid_user_id,
        "customer_name": payload.shippingAddress.name,
        "customer_phone": payload.shippingAddress.phone,
        "shipping_address": payload.shippingAddress.model_dump(),
        "items": [item.model_dump() for item in payload.items],
        "subtotal": payload.subtotal,
        "discount": payload.discount,
        "shipping_fee": payload.shippingFee,
        "total_amount": payload.total,
        "payment_method": payload.paymentMethod,
        "payment_status": "pending_delivery" if payload.paymentMethod == "cod" else "paid",
        "status": "confirmed"
    }

    try:
        order_row["order_verification_key"] = verification_key
        if payload.idempotencyKey:
            order_row["idempotency_key"] = payload.idempotencyKey
        supabase.from_("orders").insert(order_row).execute()
    except Exception:
        # Fallback if extra columns not yet migrated
        order_row.pop("order_verification_key", None)
        order_row.pop("idempotency_key", None)
        supabase.from_("orders").insert(order_row).execute()

    # Insert relational order_items
    order_items = []
    for idx, item in enumerate(payload.items):
        order_items.append({
            "id": f"item_{order_id}_{idx}",
            "order_id": order_id,
            "product_id": item.product.id,
            "product_title": item.product.title,
            "quantity": item.quantity,
            "selected_size": item.selectedSize,
            "selected_color": item.selectedColor,
            "unit_price": item.product.price
        })

    if order_items:
        supabase.from_("order_items").insert(order_items).execute()

    # Inventory decrement & 5-hour sold out tracking
    for item in payload.items:
        try:
            prod_check = supabase.from_("products").select("stock_count, description").eq("id", item.product.id).maybe_single().execute()
            if prod_check.data:
                curr_stock = int(prod_check.data.get("stock_count") or 0)
                new_stock = max(0, curr_stock - item.quantity)
                upd_prod: dict = {"stock_count": new_stock}
                if new_stock == 0:
                    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    upd_prod["sold_out_at"] = now_iso
                    desc = prod_check.data.get("description") or ""
                    clean_desc = re.sub(r"<!--sold_out_at:[^>]+-->", "", desc).strip()
                    upd_prod["description"] = f"{clean_desc}\n<!--sold_out_at:{now_iso}-->"
                try:
                    supabase.from_("products").update(upd_prod).eq("id", item.product.id).execute()
                except Exception:
                    upd_prod.pop("sold_out_at", None)
                    supabase.from_("products").update(upd_prod).eq("id", item.product.id).execute()
        except Exception:
            pass

    return {
        "success": True,
        "orderId": order_id,
        "orderNumber": order_number,
        "orderVerificationKey": verification_key,
        "status": "confirmed",
        "total": payload.total,
        "customer": payload.shippingAddress.name,
        "message": "Order placed successfully in Supabase cloud"
    }

@router.get("")
async def get_orders(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100, description="Query limit to prevent full database dump"),
    offset: int = Query(0, ge=0)
):
    """
    Get orders with pagination to avoid loading entire database at once.
    """
    query = supabase.from_("orders").select("*, order_items(*)")
    if user_id:
        query = query.eq("user_id", user_id)

    res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []

@router.get("/{order_id}")
async def get_order_by_id(order_id: str):
    """
    Get detailed order with full joined items and product references.
    """
    res = supabase.from_("orders").select("*, order_items(*, products(*)), users(*)").eq("id", order_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return res.data

@router.patch("/{order_id}/status")
async def update_order_status(order_id: str, payload: OrderStatusUpdate):
    """
    Update order packing status and notes (Merchant Admin Hub).
    """
    update_data = {"status": payload.status}
    if payload.packingNotes is not None:
        update_data["packing_notes"] = payload.packingNotes

    res = supabase.from_("orders").update(update_data).eq("id", order_id).execute()
    return {"success": True, "message": f"Order {order_id} status updated to {payload.status}"}
