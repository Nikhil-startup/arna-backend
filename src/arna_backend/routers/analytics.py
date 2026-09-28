from fastapi import APIRouter
from arna_backend.database import supabase
from arna_backend.schemas import VisitorStatsResponse

router = APIRouter(prefix="/api/analytics", tags=["Visitor Analytics"])

@router.get("", response_model=VisitorStatsResponse)
async def get_analytics():
    """
    Get live store analytics & visitor counts.
    """
    res = supabase.from_("visitor_stats").select("*").eq("id", "current_stats").maybe_single().execute()
    if res.data:
        d = res.data
        return VisitorStatsResponse(
            totalVisitors=d.get("total_visitors", 0),
            todayVisitors=d.get("today_visitors", 0),
            totalPageViews=d.get("total_page_views", 0),
            conversionRate=float(d.get("conversion_rate", 0.0)),
            activeNow=d.get("active_now", 1)
        )
    return VisitorStatsResponse(
        totalVisitors=0,
        todayVisitors=0,
        totalPageViews=0,
        conversionRate=0.0,
        activeNow=1
    )

@router.post("/visit")
async def record_visit():
    """
    Increment live visitor analytics.
    """
    stats = await get_analytics()
    new_total = stats.totalVisitors + 1
    new_today = stats.todayVisitors + 1
    new_views = stats.totalPageViews + 1

    supabase.from_("visitor_stats").update({
        "total_visitors": new_total,
        "today_visitors": new_today,
        "total_page_views": new_views
    }).eq("id", "current_stats").execute()

    return {"success": True, "totalVisitors": new_total}
