import time
import json
from collections import defaultdict
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from arna_backend.routers import auth, products, orders, coupons, analytics
from arna_backend.config import HOST, PORT

app = FastAPI(
    title="ARNA E-Commerce API",
    description="High-performance backend API for ARNA Luxury Fashion Storefront & Merchant Admin Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ----------------------------------------------------
# 1. BOT SCRAPER & ATTACK BLOCKLIST
# ----------------------------------------------------
DISALLOWED_USER_AGENTS = [
    "sqlmap", "nikto", "masscan", "dirbuster", "wpscan",
    "havij", "zgrab", "netsparker", "nmap", "scrapy"
]

# ----------------------------------------------------
# 2. RATE LIMITING ENGINE (In-Memory Sliding Window)
# ----------------------------------------------------
RATE_LIMIT_STORE: dict = defaultdict(list)

def is_rate_limited(client_ip: str, path: str) -> bool:
    now = time.time()
    window_seconds = 60.0

    # Differentiated rate limits
    if "/api/auth/send-otp" in path or "/api/auth/forgot-password" in path:
        max_requests = 10  # Prevent OTP spamming/SMS bomb
    elif "/api/orders" in path:
        max_requests = 15  # Prevent rapid order flood
    elif "/api/auth/login" in path:
        max_requests = 15  # Prevent brute force attacks
    else:
        max_requests = 80  # General catalog / viewing limit

    key = f"{client_ip}:{path.split('?')[0]}"
    timestamps = RATE_LIMIT_STORE[key]
    # Prune timestamps older than window
    timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        RATE_LIMIT_STORE[key] = timestamps
        return True

    timestamps.append(now)
    RATE_LIMIT_STORE[key] = timestamps
    return False

# ----------------------------------------------------
# 3. RATE LIMITING, ANTI-BOT & SECURITY HEADERS MIDDLEWARE
# ----------------------------------------------------
@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # A. Anti-Bot / Anti-Scraper Check
    user_agent = (request.headers.get("user-agent") or "").lower()
    for bad_bot in DISALLOWED_USER_AGENTS:
        if bad_bot in user_agent:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Automated scraping or bot download forbidden by ARNA Atelier policy."}
            )

    # B. Rate Limit Enforcement
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Honor forwarded headers from proxies
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    if request.method != "OPTIONS" and is_rate_limited(client_ip, request.url.path):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Please wait a minute before retrying."},
            headers={"Retry-After": "60"}
        )

    # C. Execute request
    response = await call_next(request)

    # D. Enforce HTTPS & Security Headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Enable CORS for local and production frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows storefront, admin portal, Vercel deployments, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all Routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(coupons.router)
app.include_router(analytics.router)

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "brand": "ARNA Luxury Fashion",
        "service": "FastAPI Backend Engine",
        "status": "online",
        "documentation": "/docs",
        "apiEndpoints": [
            "/api/auth/send-otp",
            "/api/auth/verify-otp",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
            "/api/products",
            "/api/orders",
            "/api/coupons",
            "/api/analytics"
        ]
    }

@app.get("/health", tags=["Health Check"])
async def health():
    return {"status": "healthy", "service": "arna-backend"}

def start():
    """Entry point for uv run start"""
    import uvicorn
    uvicorn.run("arna_backend.main:app", host=HOST, port=PORT, reload=True)

if __name__ == "__main__":
    start()
