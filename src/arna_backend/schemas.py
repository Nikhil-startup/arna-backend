from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any, Dict

# ----------------------------------------------------
# AUTH SCHEMAS
# ----------------------------------------------------
class SendOtpRequest(BaseModel):
    target: str = Field(..., description="Email address or phone number (+91...)")
    type: str = Field("email", description="'email' or 'phone'")
    custom_otp: Optional[str] = Field(None, description="Optional pre-generated OTP code to deliver")

class SendOtpResponse(BaseModel):
    success: bool
    otp: str
    target: str
    message: str

class VerifyOtpRequest(BaseModel):
    target: str
    otp: str

class VerifyOtpResponse(BaseModel):
    success: bool
    message: str

class AddressModel(BaseModel):
    id: Optional[str] = None
    name: str
    phone: str
    street: str
    city: str
    state: str
    pinCode: str
    isDefault: Optional[bool] = True

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    username: Optional[str] = None
    address: Optional[AddressModel] = None
    honeypot: Optional[str] = Field(None, description="Anti-bot invisible honeypot trap")

class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Email, username, or phone number")
    password: str
    honeypot: Optional[str] = Field(None, description="Anti-bot invisible honeypot trap")

class AuthUserResponse(BaseModel):
    id: str
    name: str
    username: Optional[str] = None
    email: str
    phone: str
    role: str = "customer"
    addresses: Optional[List[AddressModel]] = None

class AuthResponse(BaseModel):
    success: bool
    user: AuthUserResponse
    token: str
    message: str = "Authenticated successfully"

class ForgotPasswordRequest(BaseModel):
    identifier: str
    method: str = Field("email", description="'email' or 'phone'")

class ResetPasswordRequest(BaseModel):
    identifier: str
    otp: str
    new_password: str

# ----------------------------------------------------
# PRODUCT SCHEMAS
# ----------------------------------------------------
class ProductColor(BaseModel):
    name: str
    hex: str

class ProductBase(BaseModel):
    title: str
    slug: str
    category: str
    fit: str = "Relaxed Fit"
    price: float
    originalPrice: Optional[float] = None
    discount: Optional[int] = 0
    stockCount: int = 10
    sizes: List[str] = ["S", "M", "L", "XL"]
    colors: List[ProductColor] = []
    images: List[str] = []
    description: str = ""
    fabric: str = ""
    washCare: Optional[str] = "Machine wash cold with like colors."
    rating: Optional[float] = 4.8
    reviewsCount: Optional[int] = 100
    isNew: Optional[bool] = True
    isTrending: Optional[bool] = False
    isBestSeller: Optional[bool] = False
    soldOutAt: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    category: Optional[str] = None
    fit: Optional[str] = None
    price: Optional[float] = None
    originalPrice: Optional[float] = None
    discount: Optional[int] = None
    stockCount: Optional[int] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[ProductColor]] = None
    images: Optional[List[str]] = None
    description: Optional[str] = None
    fabric: Optional[str] = None
    washCare: Optional[str] = None
    rating: Optional[float] = None
    reviewsCount: Optional[int] = None
    isNew: Optional[bool] = None
    isTrending: Optional[bool] = None
    isBestSeller: Optional[bool] = None
    soldOutAt: Optional[str] = None

class ProductResponse(ProductBase):
    id: str
    inStock: bool = True

# ----------------------------------------------------
# ORDER SCHEMAS
# ----------------------------------------------------
class CartItemProduct(BaseModel):
    id: str
    title: str
    price: float
    images: Optional[List[str]] = []

class CartItemModel(BaseModel):
    id: Optional[str] = None
    product: CartItemProduct
    selectedSize: str
    selectedColor: str
    quantity: int

class OrderCreate(BaseModel):
    items: List[CartItemModel]
    subtotal: float
    discount: float = 0.0
    shippingFee: float = 0.0
    total: float
    shippingAddress: AddressModel
    paymentMethod: str = "upi"
    idempotencyKey: Optional[str] = None
    orderVerificationKey: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str
    packingNotes: Optional[str] = None

# ----------------------------------------------------
# COUPON SCHEMAS
# ----------------------------------------------------
class CouponValidateRequest(BaseModel):
    code: str
    orderTotal: float

class CouponValidateResponse(BaseModel):
    valid: bool
    discount: float
    code: str
    message: str

# ----------------------------------------------------
# VISITOR ANALYTICS
# ----------------------------------------------------
class VisitorStatsResponse(BaseModel):
    totalVisitors: int
    todayVisitors: int
    totalPageViews: int
    conversionRate: float
    activeNow: int
