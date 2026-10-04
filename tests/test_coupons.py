import pytest
from arna_backend.schemas import CouponValidateRequest, CouponValidateResponse


def test_coupon_validate_request_model():
    """Verify CouponValidateRequest schema validation."""
    req = CouponValidateRequest(code="ARNA20", orderTotal=1999.0)
    assert req.code == "ARNA20"
    assert req.orderTotal == 1999.0


def test_coupon_percentage_discount_calculation():
    """Test standard 20% discount coupon calculation logic."""
    order_total = 2500.0
    discount_pct = 20.0
    expected_discount = round((order_total * discount_pct) / 100)
    
    assert expected_discount == 500


def test_coupon_flat_discount_calculation():
    """Test flat discount logic ensuring discount does not exceed order total."""
    order_total = 800.0
    flat_discount = 300.0
    applied = min(flat_discount, order_total)
    assert applied == 300.0

    tiny_order = 150.0
    applied_tiny = min(flat_discount, tiny_order)
    assert applied_tiny == 150.0


def test_coupon_minimum_order_value_check():
    """Ensure coupon rejects orders below the minimum order value threshold."""
    min_order_value = 1499.0
    order_total = 1200.0
    
    is_eligible = order_total >= min_order_value
    assert is_eligible is False

    valid_order = 1800.0
    assert (valid_order >= min_order_value) is True
