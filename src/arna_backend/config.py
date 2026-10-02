import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://zxsyrzputfsclarigazm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_3wAFaiAeBRNvaq4_3bJYww_Iz__v_tf")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Email Dispatch (Resend HTTPS API & Gmail SMTP)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "ARNA Luxury Fashion <onboarding@resend.dev>")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# SMS Gateway Configuration (Twilio or Fast2SMS)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")

# Payment Gateway Configuration (Razorpay & Direct UPI QR)
ENABLE_ONLINE_PAYMENTS = os.getenv("ENABLE_ONLINE_PAYMENTS", "true").lower() in ("true", "1", "yes")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
STORE_UPI_ID = os.getenv("STORE_UPI_ID", "arna@okhdfcbank")
STORE_UPI_NAME = os.getenv("STORE_UPI_NAME", "ARNA Luxury Fashion")

