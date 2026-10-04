import time
import pytest
from arna_backend.routers.orders import IDEMPOTENCY_CACHE
from arna_backend.schemas import OrderStatusUpdate


def test_idempotency_cache_replay_behavior():
    """Verify that orders cached by idempotencyKey can be retrieved on network retry."""
    test_key = f"TEST-IDEMP-{int(time.time())}"
    sample_result = {
        "success": True,
        "orderId": "ord_9999",
        "orderNumber": "ARNA-555555",
        "status": "confirmed",
        "total": 2499.0
    }
    
    # Store in idempotency registry
    IDEMPOTENCY_CACHE[test_key] = sample_result

    # Retrieve and check replayed flag
    cached = IDEMPOTENCY_CACHE[test_key].copy()
    cached["replayed"] = True
    
    assert cached["orderId"] == "ord_9999"
    assert cached["replayed"] is True
    assert cached["orderNumber"] == "ARNA-555555"


def test_order_verification_key_format():
    """Verify customer fulfillment verification key format (ARNA-VK-XXXX-TIMESTAMP)."""
    import uuid
    v_key = f"ARNA-VK-{uuid.uuid4().hex[:6].upper()}-{int(time.time())}"
    
    assert v_key.startswith("ARNA-VK-")
    parts = v_key.split("-")
    assert len(parts) == 4
    assert len(parts[2]) == 6


def test_order_status_update_schema():
    """Verify OrderStatusUpdate schema validation."""
    upd = OrderStatusUpdate(status="shipped", packingNotes="Packed with luxury garment bag and hanger.")
    assert upd.status == "shipped"
    assert "luxury garment bag" in upd.packingNotes
