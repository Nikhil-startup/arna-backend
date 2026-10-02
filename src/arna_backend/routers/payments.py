import time
import os
import hmac
import hashlib
import logging
import re
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, status
from arna_backend.config import (
    ENABLE_ONLINE_PAYMENTS,
    RAZORPAY_KEY_ID, 
    RAZORPAY_KEY_SECRET, 
    STORE_UPI_ID, 
    STORE_UPI_NAME
)
from arna_backend.schemas import (
    PaymentConfigResponse,
    RazorpayCreateOrderRequest,
    RazorpayCreateOrderResponse,
    RazorpayVerifyRequest,
    RazorpayVerifyResponse,
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
        razorpayEnabled=ENABLE_ONLINE_PAYMENTS and is_active,
        razorpayKeyId=RAZORPAY_KEY_ID if is_active else "",
        isTestMode=not is_active or "test" in (RAZORPAY_KEY_ID or "").lower(),
        upiEnabled=ENABLE_ONLINE_PAYMENTS,
        storeUpiId=STORE_UPI_ID or "arna@okhdfcbank",
        storeUpiName=STORE_UPI_NAME or "ARNA Luxury Fashion",
        codEnabled=True
    )

@router.post("/create-order", response_model=RazorpayCreateOrderResponse)
async def create_razorpay_order(payload: RazorpayCreateOrderRequest):
    """
    Creates an order on the payment gateway or reuses the existing order
    for the active checkout idempotency key to prevent double charging.
    """
    if not ENABLE_ONLINE_PAYMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Online payment gateway is temporarily disabled. Please complete checkout with Cash on Delivery."
        )

    if not payload.idempotencyKey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key required for safe payment creation"
        )

    clean_key = payload.idempotencyKey.strip()

    # 1. Idempotency Check: Reuse existing gateway order if already generated for this attempt
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

    # 2. Live / Test Gateway Interaction
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
                    "store": "ARNA Luxury Fashion"
                }
            }
            rzp_order = client.order.create(data=rzp_payload)

            result = {
                "success": True,
                "gatewayOrderId": rzp_order["id"],
                "amount": rzp_order["amount"],
                "currency": rzp_order["currency"],
                "keyId": RAZORPAY_KEY_ID,
                "isTestMode": "test" in RAZORPAY_KEY_ID.lower(),
                "replayed": False
            }
            GATEWAY_ORDERS_CACHE[clean_key] = result
            return result
        except Exception as e:
            logging.error(f"Razorpay order creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment gateway initiation error: {str(e)}"
            )

    # 3. Sandbox Simulation (When keys are not yet configured in .env)
    simulated_order_id = f"order_sim_{int(time.time())}_{clean_key[-6:]}"
    result = {
        "success": True,
        "gatewayOrderId": simulated_order_id,
        "amount": amount_paise,
        "currency": payload.currency or "INR",
        "keyId": "rzp_test_sandbox_mode",
        "isTestMode": True,
        "replayed": False
    }
    GATEWAY_ORDERS_CACHE[clean_key] = result
    return result

@router.post("/verify", response_model=RazorpayVerifyResponse)
async def verify_razorpay_payment(payload: RazorpayVerifyRequest):
    """
    Cryptographically verifies the HMAC SHA256 payment signature
    generated by Razorpay upon successful checkout.
    """
    if not payload.razorpay_order_id or not payload.razorpay_payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required gateway verification identifiers"
        )

    # Sandbox simulation check
    if payload.razorpay_order_id.startswith("order_sim_") or not has_active_razorpay_keys():
        return RazorpayVerifyResponse(
            success=True,
            verified=True,
            message="Sandbox test payment signature verified successfully."
        )

    # Cryptographic signature verification using server-side secret key
    try:
        body_to_sign = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8")
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            body_to_sign,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cryptographic payment signature. Authorization rejected."
            )

        return RazorpayVerifyResponse(
            success=True,
            verified=True,
            message="Payment signature cryptographically verified and authorized."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification computation error: {str(e)}"
        )

@router.post("/verify-upi-utr")
async def verify_upi_utr(payload: UpiVerifyRequest):
    """
    Validates a 12-digit UPI UTR / Transaction Reference Number submitted
    by customers using direct UPI QR transfer (Option 4).
    """
    if not ENABLE_ONLINE_PAYMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct UPI payments are temporarily disabled. Please use Cash on Delivery."
        )

    clean_utr = payload.utrNumber.strip().replace(" ", "")

    # Standard bank UTR is 12 alphanumeric/numeric digits
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
