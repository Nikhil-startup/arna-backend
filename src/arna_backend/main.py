from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from arna_backend.routers import auth, products, orders, coupons, analytics
from arna_backend.config import HOST, PORT

app = FastAPI(
    title="ARNA E-Commerce API",
    description="High-performance backend API for ARNA Luxury Fashion Storefront & Merchant Admin Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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
