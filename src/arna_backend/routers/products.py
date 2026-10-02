from fastapi import APIRouter, HTTPException, Query, Response, status
from typing import List, Optional
from arna_backend.database import supabase
from arna_backend.schemas import ProductResponse, ProductCreate, ProductBase

router = APIRouter(prefix="/api/products", tags=["Products Catalog"])

import re

def extract_sold_out_at(row: dict) -> Optional[str]:
    if row.get("sold_out_at"):
        return str(row["sold_out_at"])
    desc = row.get("description") or ""
    match = re.search(r"<!--sold_out_at:([^>]+)-->", desc)
    if match:
        return match.group(1)
    return None

@router.get("", response_model=List[ProductResponse])
async def get_products(
    response: Response,
    category: Optional[str] = Query(None, description="Filter by category (shirts, t-shirts, etc.)"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    search: Optional[str] = Query(None, description="Search keyword in title or description"),
    sort_by: Optional[str] = Query(None, description="price-low-high, price-high-low, newest, popular"),
    limit: int = Query(50, ge=1, le=100, description="Page limit to avoid loading whole database"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Fetch live clothing products from Supabase PostgreSQL with pagination and optional filters.
    """
    query = supabase.from_("products").select("*")

    if category and category != "all":
        query = query.eq("category", category)
    if min_price is not None:
        query = query.gte("price", min_price)
    if max_price is not None:
        query = query.lte("price", max_price)

    # Avoid loading whole database at once
    res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    items = res.data or []

    # Map database row to ProductResponse
    result = []
    for row in items:
        stock = row.get("stock_count", 10)
        sold_out_timestamp = extract_sold_out_at(row) or (row.get("created_at") if stock <= 0 else None)
        clean_desc = re.sub(r"<!--sold_out_at:[^>]+-->", "", row.get("description", "")).strip()

        prod = ProductResponse(
            id=row["id"],
            title=row["title"],
            slug=row.get("slug", row["title"].lower().replace(" ", "-")),
            category=row.get("category", "shirts"),
            fit=row.get("fit", "Relaxed Fit"),
            price=float(row.get("price", 0)),
            originalPrice=float(row.get("original_price", row.get("price", 0))),
            discount=row.get("discount", 0),
            stockCount=stock,
            inStock=(stock > 0),
            soldOutAt=sold_out_timestamp,
            sizes=row.get("sizes", ["S", "M", "L", "XL"]),
            colors=row.get("colors", [{"name": "Classic", "hex": "#111827"}]),
            images=row.get("images", []),
            description=clean_desc,
            fabric=row.get("fabric", ""),
            washCare=row.get("wash_care", "Machine wash cold."),
            rating=float(row.get("rating", 4.8)),
            reviewsCount=int(row.get("reviews_count", 100)),
            isNew=bool(row.get("is_new", True)),
            isTrending=bool(row.get("is_trending", False)),
            isBestSeller=bool(row.get("is_bestseller", False))
        )

        # Keyword search filter
        if search and search.strip():
            q = search.lower().strip()
            if not (q in prod.title.lower() or q in prod.description.lower() or q in prod.category.lower()):
                continue

        result.append(prod)

    # Sorting
    if sort_by == "price-low-high":
        result.sort(key=lambda x: x.price)
    elif sort_by == "price-high-low":
        result.sort(key=lambda x: x.price, reverse=True)
    elif sort_by == "newest":
        result.sort(key=lambda x: 1 if x.isNew else 0, reverse=True)

    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return result

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """
    Get detailed product by ID.
    """
    res = supabase.from_("products").select("*").eq("id", product_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    row = res.data
    return ProductResponse(
        id=row["id"],
        title=row["title"],
        slug=row.get("slug", row["title"].lower().replace(" ", "-")),
        category=row.get("category", "shirts"),
        fit=row.get("fit", "Relaxed Fit"),
        price=float(row.get("price", 0)),
        originalPrice=float(row.get("original_price", row.get("price", 0))),
        discount=row.get("discount", 0),
        stockCount=row.get("stock_count", 10),
        inStock=(row.get("stock_count", 10) > 0),
        sizes=row.get("sizes", ["S", "M", "L", "XL"]),
        colors=row.get("colors", [{"name": "Classic", "hex": "#111827"}]),
        images=row.get("images", []),
        description=row.get("description", ""),
        fabric=row.get("fabric", ""),
        washCare=row.get("wash_care", "Machine wash cold."),
        rating=float(row.get("rating", 4.8)),
        reviewsCount=int(row.get("reviews_count", 100)),
        isNew=bool(row.get("is_new", True)),
        isTrending=bool(row.get("is_trending", False)),
        isBestSeller=bool(row.get("is_bestseller", False))
    )

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate):
    """
    Add a new product to the catalog (Merchant Admin).
    """
    import time
    prod_id = f"prod_{int(time.time() * 1000)}"
    row = {
        "id": prod_id,
        "title": product.title,
        "slug": product.slug,
        "category": product.category,
        "fit": product.fit,
        "price": product.price,
        "original_price": product.originalPrice or product.price,
        "discount": product.discount or 0,
        "stock_count": product.stockCount,
        "sizes": product.sizes,
        "colors": [c.model_dump() for c in product.colors],
        "images": product.images,
        "description": product.description,
        "fabric": product.fabric,
        "wash_care": product.washCare,
        "rating": product.rating or 4.8,
        "reviews_count": product.reviewsCount or 100,
        "is_new": product.isNew,
        "is_trending": product.isTrending,
        "is_bestseller": product.isBestSeller
    }

    res = supabase.from_("products").insert(row).execute()
    return await get_product(prod_id)

@router.delete("/{product_id}")
async def delete_product(product_id: str):
    """
    Delete a product from the catalog. Cascades any referencing order_items first.
    """
    try:
        supabase.from_("order_items").delete().eq("product_id", product_id).execute()
    except Exception as e:
        pass
    supabase.from_("products").delete().eq("id", product_id).execute()
    return {"success": True, "message": f"Product {product_id} deleted"}
