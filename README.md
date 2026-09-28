# ARNA Luxury Fashion — FastAPI Backend Engine (Powered by UV)

A high-performance, asynchronous REST API backend built with **FastAPI** and managed with **uv** (Astral's ultra-fast Python package and project manager). Directly integrated with your **Supabase PostgreSQL** cloud database.

---

## 🚀 Quick Start with UV

### 1. Run the Server
From the `D:\arna-backend` directory:

```bash
# Using UV to run the preconfigured start script
python -m uv run start

# Or directly with uvicorn
python -m uv run uvicorn arna_backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at:
- **API Base URL**: `http://localhost:8000`
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Interactive Documentation**: `http://localhost:8000/redoc`

---

## 📡 API Endpoints Overview

### 1. Authentication & OTP (`/api/auth`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/send-otp` | Generates and sends a 6-digit OTP to a mobile phone (+91...) or email/Gmail |
| `POST` | `/api/auth/verify-otp` | Validates the 6-digit OTP code |
| `POST` | `/api/auth/register` | Creates a new customer account, sets username, hashes password, and saves delivery address |
| `POST` | `/api/auth/login` | Authenticates customer by Email, Phone number, or Username + Password |
| `POST` | `/api/auth/forgot-password` | Dispatches password reset OTP to registered email or mobile phone |
| `POST` | `/api/auth/reset-password` | Verifies reset OTP and updates password in database |

### 2. Products Catalog (`/api/products`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/products` | Lists products with optional filters (`category`, `min_price`, `max_price`, `search`, `sort_by`) |
| `GET` | `/api/products/{id}` | Gets single detailed product |
| `POST` | `/api/products` | Adds a new luxury clothing piece (Merchant Admin) |
| `DELETE` | `/api/products/{id}` | Deletes a product from the catalog |

### 3. Orders & Fulfillment (`/api/orders`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/orders` | Places order with relational `order_items` and ensures `user_id` foreign key integrity |
| `GET` | `/api/orders` | Fetches orders (pass `?user_id=...` for customer or omit for Merchant Admin) |
| `GET` | `/api/orders/{id}` | Fetches full relational order record with products and shipping details |
| `PATCH` | `/api/orders/{id}/status` | Updates order fulfillment status (`confirmed`, `packing`, `shipped`, `delivered`) and packing checklist notes |

### 4. Discounts & Coupons (`/api/coupons`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/coupons` | Lists all active discount coupons |
| `POST` | `/api/coupons/validate` | Validates promo code against cart subtotal and calculates discount |
| `POST` | `/api/coupons` | Creates a new coupon (Merchant Admin) |
| `PATCH` | `/api/coupons/{id}/toggle` | Activates or pauses a coupon |

### 5. Visitor Analytics (`/api/analytics`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/analytics` | Gets real-time visitor counts, today's visits, page views, and conversion rates |
| `POST` | `/api/analytics/visit` | Increments page view and visitor counter in real-time |

---

## 🛠️ Project Structure

```
D:\arna-backend\
├── .env                     # Supabase cloud credentials & server config
├── pyproject.toml           # UV project definition & dependencies
├── uv.lock                  # Pinned deterministic lockfile
├── start.ps1                # 1-click startup script
├── src/
│   └── arna_backend/
│       ├── __init__.py
│       ├── config.py        # Environment variables loader
│       ├── database.py      # Supabase PostgreSQL client connection
│       ├── schemas.py       # Pydantic request & response models
│       ├── main.py          # FastAPI application & CORS middleware
│       └── routers/
│           ├── auth.py      # OTP & Authentication routes
│           ├── products.py  # Products catalog routes
│           ├── orders.py    # Order placement & fulfillment routes
│           ├── coupons.py   # Discount coupon routes
│           └── analytics.py # Visitor analytics routes
```
