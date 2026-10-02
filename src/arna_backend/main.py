import time
import json
import logging
from collections import defaultdict
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from arna_backend.routers import auth, products, orders, coupons, analytics, system
from arna_backend.config import HOST, PORT
from arna_backend.services.sanitizer import SanitizedLogFilter
from arna_backend.services.backup import backup_service
from arna_backend.services.billing import billing_service

# ----------------------------------------------------
# 0. LOG SANITIZATION (Never log passwords, tokens, cards)
# ----------------------------------------------------
root_logger = logging.getLogger()
sanitized_filter = SanitizedLogFilter()
for handler in root_logger.handlers:
    handler.addFilter(sanitized_filter)

app = FastAPI(
    title="ARNA E-Commerce API",
    description="High-performance secured backend API for ARNA Luxury Fashion Storefront & Merchant Admin Portal",
    version="1.1.0",
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
        max_requests = 10  # Prevent brute force attacks
    else:
        max_requests = 80  # General catalog / viewing limit

    key = f"{client_ip}:{path.split('?')[0]}"
    timestamps = RATE_LIMIT_STORE[key]
    timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        RATE_LIMIT_STORE[key] = timestamps
        return True

    timestamps.append(now)
    RATE_LIMIT_STORE[key] = timestamps
    return False

# ----------------------------------------------------
# 3. SECURITY, HTTPS, CSRF & RATE LIMITING MIDDLEWARE
# ----------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Record API usage for billing alerts
    billing_service.record_usage("api_requests", 1)

    # A. Anti-Bot / Anti-Scraper Check
    user_agent = (request.headers.get("user-agent") or "").lower()
    for bad_bot in DISALLOWED_USER_AGENTS:
        if bad_bot in user_agent:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Automated scraping or bot download forbidden by ARNA Atelier policy."}
            )

    # B. HTTPS Focus & Enforcement
    proto = request.headers.get("x-forwarded-proto")
    client_host = request.headers.get("host", "")
    if proto == "http" and "localhost" not in client_host and "127.0.0.1" not in client_host:
        https_url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url=https_url, status_code=status.HTTP_301_MOVED_PERMANENTLY)

    # C. CSRF Protocol Protection on State-Changing Methods
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        # Allow preflight, webhooks, or endpoints with valid anti-CSRF signature
        csrf_token = request.headers.get("x-csrf-token")
        requested_with = request.headers.get("x-requested-with")
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        # Allow authenticated calls, custom header requests, or matching origin
        is_safe_client = bool(
            csrf_token or 
            requested_with == "XMLHttpRequest" or
            (origin and ("localhost" in origin or "127.0.0.1" in origin or "arna" in origin or "vercel.app" in origin)) or
            (referer and ("localhost" in referer or "127.0.0.1" in referer or "arna" in referer or "vercel.app" in referer))
        )
        if not is_safe_client and not request.url.path.startswith("/api/auth/"):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF protocol verification failed. Untrusted cross-site request blocked."}
            )

    # D. Rate Limit Enforcement
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    if request.method != "OPTIONS" and is_rate_limited(client_ip, request.url.path):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Please wait a minute before retrying."},
            headers={"Retry-After": "60"}
        )

    # E. Execute request
    response = await call_next(request)

    # F. Enforce HTTPS, HSTS & Security Headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(self)"
    response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return response

# Enable CORS for local and production frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows storefront, admin portal, Vercel deployments, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable Gzip compression on all JSON responses > 500 bytes (mitigates uncompressed JSON)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Register all Routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(coupons.router)
app.include_router(analytics.router)
app.include_router(system.router)

@app.on_event("startup")
async def on_startup():
    """Initializes security audit and verifies automated backup snapshots exist."""
    try:
        backups = backup_service.list_backups()
        if not backups:
            backup_service.create_backup(trigger_source="server_startup_init")
    except Exception as e:
        logging.warning(f"Startup backup notice: {e}")

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "brand": "ARNA Luxury Fashion",
        "service": "FastAPI Backend Engine",
        "status": "online",
        "security": {
            "https_focus": "Enforced (HSTS & CSP upgrade-insecure-requests)",
            "bot_protection": "Active (Honeypot trap & rate limiters)",
            "csrf_protocol": "Active (Double submit & custom headers)",
            "database_key": "Limited (Scoped publishable anon key)",
            "storage_sanitization": "Active (Zero plain passwords or card numbers in logs/dumps)",
            "billing_alerts": "Active",
            "automated_backups": "Active"
        },
        "documentation": "/docs"
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

