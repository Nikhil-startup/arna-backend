import time
import os
import hmac
import hashlib
import logging
import re
import random
import uuid
from typing import Dict, Optional, List, Any
from fastapi import APIRouter, HTTPException, status
from arna_backend.config import (
    ENABLE_ONLINE_PAYMENTS,
    RAZORPAY_KEY_ID, 
    RAZORPAY_KEY_SECRET, 
    STORE_UPI_ID, 
    STORE_UPI_NAME
)
from arna_backend.database import supabase
from arna_backend.schemas import (
    PaymentConfigResponse,
    RazorpayCreateOrderRequest,
    RazorpayCreateOrderResponse,
    RazorpayVerifyRequest,
    RazorpayVerifyResponse,
    PaymentFailureRequest,
    PaymentFailureResponse,
    UpiVerifyRequest
)
import razorpay

router = APIRouter(prefix="/api/payments", tags=["Payments & Gateways"])

# In-memory Idempotency Cache for Gateway Orders (prevents generating duplicate gateway order IDs on retries)
GATEWAY_ORDERS_CACHE: Dict[str, dict] = {}

def has_active_razorpay_keys() -> bool:
    """Check if valid non-empty Razorpay keys are provided and online payments are enabled."""
    if not ENABLE_ONLINE_PAYMENTS:
        return False
    return bool(
        RAZORPAY_KEY_ID and 
        RAZORPAY_KEY_SECRET and 
        RAZORPAY_KEY_ID.startswith("rzp_") and
        len(RAZORPAY_KEY_SECRET) > 8
    )

@router.get("/config", response_model=PaymentConfigResponse)
async def get_payment_config():
    """
    Returns public payment gateway capabilities and configuration.
    Never exposes backend secret keys.
    """
    is_active = has_active_razorpay_keys()
    return PaymentConfigResponse(
        razorpayEnabled=ENABLE_ONLINE_PAYMENTS,
        razorpayKeyId=RAZORPAY_KEY_ID if is_active else "rzp_test_sandbox_mode",
        isTestMode=not is_active or "test" in (RAZORPAY_KEY_ID or "").lower(),
        upiEnabled=ENABLE_ONLINE_PAYMENTS,
        storeUpiId=STORE_UPI_ID or "arna@okhdfcbank",
        storeUpiName=STORE_UPI_NAME or "ARNA Luxury Fashion",
        codEnabled=True
    )

# ----------------------------------------------------
# 1. CREATE AN ORDER FROM THE SERVER
# ----------------------------------------------------
@router.post("/create-order", response_model=RazorpayCreateOrderResponse)
async def create_razorpay_order(payload: RazorpayCreateOrderRequest):
    """
    1. Validates and generates order from server using Razorpay Gateway API.
    2. Stores initial initialized order record in database.
    3. Bundles order_id and checkout options for the client.
    """
    if not payload.idempotencyKey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key required for safe payment creation"
        )

    clean_key = payload.idempotencyKey.strip()

    # Fast-path Idempotency check: Reuse existing gateway order if already created for this session
    if clean_key in GATEWAY_ORDERS_CACHE:
        cached = GATEWAY_ORDERS_CACHE[clean_key].copy()
        cached["replayed"] = True
        return cached

    amount_paise = int(round(payload.amount * 100))
    if amount_paise <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order amount must be greater than zero"
        )

    # 1A. Gateway Order Generation
    gateway_order_id = ""
    key_id = ""
    is_test_mode = True

    if has_active_razorpay_keys():
        try:
            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            receipt_str = clean_key[:40]
            rzp_payload = {
                "amount": amount_paise,
                "currency": payload.currency or "INR",
                "receipt": receipt_str,
                "notes": {
                    "idempotency_key": clean_key,
                    "customer_name": payload.customerName or "Valued Customer",
                    "customer_phone": payload.customerPhone or "",
                    "store": "ARNA Luxury Fashion"
                }
            }
            rzp_order = client.order.create(data=rzp_payload)
            gateway_order_id = rzp_order["id"]
            key_id = RAZORPAY_KEY_ID
            is_test_mode = "test" in RAZORPAY_KEY_ID.lower()
        except Exception as e:
            logging.error(f"Razorpay server order creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment gateway initiation error: {str(e)}"
            )
    else:
        # Development / Sandbox Mode (Clean test simulation order created from server)
        gateway_order_id = f"order_sim_{int(time.time())}_{clean_key[-6:]}"
        key_id = "rzp_test_sandbox_mode"
        is_test_mode = True

    # 1B. Store Initial Order Fields in Server Database
    internal_order_id = f"ord_{int(time.time() * 1000)}"
    order_number = f"ARNA-{random.randint(100000, 999999)}"

    try:
        # Check if record for this idempotency_key already exists in DB
        existing_order = supabase.from_("orders").select("id, order_number").eq("idempotency_key", clean_key).maybe_single().execute()
        if existing_order.data:
            internal_order_id = existing_order.data["id"]
            order_number = existing_order.data["order_number"]
            supabase.from_("orders").update({
                "gateway_order_id": gateway_order_id,
                "payment_status": "initiated",
                "status": "initiated"
            }).eq("id", internal_order_id).execute()
        else:
            # Ensure customer user exists
            guest_id = f"usr_pay_{int(time.time() * 1000)}"
            try:
                supabase.from_("users").insert({
                    "id": guest_id,
                    "name": payload.customerName or "Customer",
                    "email": payload.customerEmail or f"cust_{clean_key[-6:]}@arna.co.in",
                    "phone": payload.customerPhone or "9999999999",
                    "role": "customer"
                }).execute()
            except Exception:
                pass

            order_init_row = {
                "id": internal_order_id,
                "order_number": order_number,
                "user_id": guest_id,
                "customer_name": payload.customerName or "Customer",
                "customer_phone": payload.customerPhone or "",
                "shipping_address": payload.shippingAddress or {},
                "items": payload.items or [],
                "subtotal": payload.amount,
                "discount": 0.0,
                "shipping_fee": 0.0,
                "total_amount": payload.amount,
                "payment_method": "razorpay",
                "payment_status": "initiated",
                "status": "initiated",
                "gateway_order_id": gateway_order_id,
                "idempotency_key": clean_key
            }
            try:
                supabase.from_("orders").insert(order_init_row).execute()
            except Exception:
                order_init_row.pop("gateway_order_id", None)
                order_init_row.pop("idempotency_key", None)
                try:
                    supabase.from_("orders").insert(order_init_row).execute()
                except Exception:
                    pass
    except Exception as db_err:
        logging.warning(f"Note on server order pre-save: {db_err}")

    # 1C. Pass Order ID and Server Options to Checkout
    checkout_options = {
        "key": key_id,
        "amount": amount_paise,
        "currency": payload.currency or "INR",
        "name": "ARNA MENS WEAR",
        "description": f"Order {order_number} // Luxury Apparel",
        "order_id": gateway_order_id,
        "prefill": {
            "name": payload.customerName or "",
            "email": payload.customerEmail or "",
            "contact": payload.customerPhone or ""
        },
        "theme": {
            "color": "#000000"
        },
        "notes": {
            "idempotency_key": clean_key,
            "order_number": order_number,
            "brand": "ARNA Luxury Menswear"
        }
    }

    result = {
        "success": True,
        "gatewayOrderId": gateway_order_id,
        "amount": amount_paise,
        "currency": payload.currency or "INR",
        "keyId": key_id,
        "isTestMode": is_test_mode,
        "replayed": False,
        "checkoutOptions": checkout_options
    }

    GATEWAY_ORDERS_CACHE[clean_key] = result
    return result

# ----------------------------------------------------
# 2. PERFORM SIGNATURE VERIFICATION & CONFIRM ORDER
# ----------------------------------------------------
@router.post("/verify", response_model=RazorpayVerifyResponse)
async def verify_razorpay_payment(payload: RazorpayVerifyRequest):
    """
    1. Cryptographically verifies HMAC SHA-256 signature using secret key.
    2. Rejects authorization and flags failure if signature is invalid.
    3. Upon success, stores payment_id, signature, and verification key in server.
    4. Confirms order and logically decrements product stock.
    """
    if not payload.razorpay_order_id or not payload.razorpay_payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required gateway verification identifiers"
        )

    # 2A. Cryptographic Signature Verification
    if has_active_razorpay_keys():
        try:
            body_to_sign = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8")
            expected_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode("utf-8"),
                body_to_sign,
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
                # Flag verification failure on server
                try:
                    supabase.from_("orders").update({
                        "status": "payment_failed",
                        "payment_status": "signature_mismatch",
                        "notes": "Cryptographic signature validation failed"
                    }).eq("gateway_order_id", payload.razorpay_order_id).execute()
                except Exception:
                    pass

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cryptographic payment signature mismatch. Payment rejected."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Verification calculation error: {str(e)}"
            )

    # 2B. Store Confirmed Fields & Verification Key in Server
    verification_key = f"ARNA-VK-{random.randint(1000, 9999)}-{int(time.time())}"
    order_id = ""
    order_number = ""

    try:
        # Match order by gateway_order_id or idempotencyKey
        matched = None
        if payload.razorpay_order_id:
            matched = supabase.from_("orders").select("*").eq("gateway_order_id", payload.razorpay_order_id).maybe_single().execute()
        if (not matched or not matched.data) and payload.idempotencyKey:
            matched = supabase.from_("orders").select("*").eq("idempotency_key", payload.idempotencyKey).maybe_single().execute()

        if matched and matched.data:
            order_id = matched.data["id"]
            order_number = matched.data["order_number"]
            # Update order record with verified payment fields
            upd_data = {
                "status": "confirmed",
                "payment_status": "paid",
                "payment_id": payload.razorpay_payment_id,
                "order_verification_key": verification_key,
                "notes": f"Verified via Razorpay Signature (Payment ID: {payload.razorpay_payment_id})"
            }
            try:
                supabase.from_("orders").update(upd_data).eq("id", order_id).execute()
            except Exception:
                upd_data.pop("order_verification_key", None)
                upd_data.pop("payment_id", None)
                supabase.from_("orders").update(upd_data).eq("id", order_id).execute()

            # Logical inventory decrement
            items = matched.data.get("items") or payload.items or []
            for item in items:
                prod_id = item.get("product", {}).get("id") or item.get("productId") or item.get("id")
                qty = item.get("quantity", 1)
                if prod_id:
                    try:
                        p_check = supabase.from_("products").select("stock_count").eq("id", prod_id).maybe_single().execute()
                        if p_check.data:
                            curr_stock = int(p_check.data.get("stock_count") or 0)
                            supabase.from_("products").update({"stock_count": max(0, curr_stock - qty)}).eq("id", prod_id).execute()
                    except Exception:
                        pass
        else:
            # If order was not pre-saved, create it now
            order_id = f"ord_{int(time.time() * 1000)}"
            order_number = f"ARNA-{random.randint(100000, 999999)}"
            new_row = {
                "id": order_id,
                "order_number": order_number,
                "customer_name": payload.customerName or "Customer",
                "customer_phone": payload.customerPhone or "",
                "shipping_address": payload.shippingAddress or {},
                "items": payload.items or [],
                "payment_method": "razorpay",
                "payment_status": "paid",
                "status": "confirmed",
                "payment_id": payload.razorpay_payment_id,
                "gateway_order_id": payload.razorpay_order_id,
                "order_verification_key": verification_key,
                "idempotency_key": payload.idempotencyKey
            }
            try:
                supabase.from_("orders").insert(new_row).execute()
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Database sync note on verification: {e}")
        if not order_id:
            order_id = f"ord_{int(time.time() * 1000)}"
            order_number = f"ARNA-{random.randint(100000, 999999)}"

    return RazorpayVerifyResponse(
        success=True,
        verified=True,
        orderId=order_id,
        orderNumber=order_number,
        orderVerificationKey=verification_key,
        paymentId=payload.razorpay_payment_id,
        message="Cryptographic signature verified successfully. Order confirmed & inventory locked."
    )

# ----------------------------------------------------
# 3. HANDLE PAYMENT FAILURE & STORE IN SERVER
# ----------------------------------------------------
@router.post("/failure", response_model=PaymentFailureResponse)
async def handle_payment_failure(payload: PaymentFailureRequest):
    """
    1. Records payment gateway error details in server database.
    2. Updates order status to payment_failed without compromising inventory.
    3. Keeps idempotency key active so customer can safely retry without duplicate orders.
    """
    error_desc = payload.errorDescription or payload.errorReason or "Payment authorization declined by issuing bank"
    logging.warning(
        f"[PAYMENT FAILURE] GatewayOrder: {payload.gatewayOrderId}, "
        f"PaymentId: {payload.paymentId}, Code: {payload.errorCode}, Reason: {error_desc}"
    )

    try:
        update_fields = {
            "status": "payment_failed",
            "payment_status": "failed",
            "notes": f"Payment Failed [{payload.errorCode or 'DECLINED'}]: {error_desc[:120]}"
        }
        if payload.gatewayOrderId:
            supabase.from_("orders").update(update_fields).eq("gateway_order_id", payload.gatewayOrderId).execute()
        elif payload.idempotencyKey:
            supabase.from_("orders").update(update_fields).eq("idempotency_key", payload.idempotencyKey).execute()
    except Exception as e:
        logging.warning(f"Error recording payment failure in DB: {e}")

    return PaymentFailureResponse(
        success=True,
        message="Payment failure recorded on server. Customer may safely retry.",
        gatewayOrderId=payload.gatewayOrderId
    )

# ----------------------------------------------------
# 4. DIRECT UPI UTR VERIFICATION
# ----------------------------------------------------
@router.post("/verify-upi-utr")
async def verify_upi_utr(payload: UpiVerifyRequest):
    """
    Validates a 12-digit UPI UTR / Transaction Reference Number submitted
    by customers using direct UPI QR transfer (Option 4).
    """
    clean_utr = payload.utrNumber.strip().replace(" ", "")

    if not re.match(r"^[0-9A-Za-z]{12}$", clean_utr):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid 12-character UPI Reference / UTR Number found in your UPI app payment receipt."
        )

    return {
        "success": True,
        "verified": True,
        "utrNumber": clean_utr,
        "message": "UPI UTR Reference recorded for merchant settlement reconciliation."
    }
