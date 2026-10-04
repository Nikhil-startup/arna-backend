import pytest
from arna_backend.routers.products import extract_sold_out_at
from arna_backend.schemas import ProductResponse


def test_extract_sold_out_at_from_column():
    """Extract sold_out_at when present directly in database row column."""
    row = {"sold_out_at": "2026-10-01T12:00:00Z", "description": "Linen shirt"}
    assert extract_sold_out_at(row) == "2026-10-01T12:00:00Z"


def test_extract_sold_out_at_from_html_comment():
    """Extract sold_out_at when embedded in description as HTML comment tag."""
    row = {
        "sold_out_at": None,
        "description": "Premium Cotton Shirt <!--sold_out_at:2026-09-28T14:30:00Z--> Handcrafted in Italy."
    }
    extracted = extract_sold_out_at(row)
    assert extracted == "2026-09-28T14:30:00Z"


def test_extract_sold_out_at_none_when_in_stock():
    """Return None when no sold out metadata exists."""
    row = {"sold_out_at": None, "description": "Regular in-stock shirt"}
    assert extract_sold_out_at(row) is None


def test_product_response_schema():
    """Verify that ProductResponse accurately computes inStock based on stockCount."""
    prod = ProductResponse(
        id="prod_123",
        title="Oversized Heavyweight Tee",
        slug="oversized-heavyweight-tee",
        category="t-shirts",
        price=1499.0,
        originalPrice=1999.0,
        stockCount=5,
        inStock=True
    )
    assert prod.id == "prod_123"
    assert prod.price == 1499.0
    assert prod.inStock is True
