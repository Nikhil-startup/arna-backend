import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from arna_backend.config import (
    GMAIL_USER, GMAIL_APP_PASSWORD,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
    FAST2SMS_API_KEY
)

def send_email_otp(to_email: str, otp_code: str) -> dict:
    """
    Send real 6-digit OTP code to customer's Gmail or email address via Gmail SMTP.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return {
            "delivered": False,
            "channel": "simulation",
            "message": "Gmail credentials not configured in .env. Code displayed on-screen for testing."
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your ARNA Verification Code is {otp_code}"
        msg["From"] = f"ARNA Luxury Fashion <{GMAIL_USER}>"
        msg["To"] = to_email

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fafafa; padding: 20px; }}
            .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .brand {{ font-size: 20px; font-weight: 900; letter-spacing: 0.15em; text-transform: uppercase; color: #000000; text-align: center; margin-bottom: 24px; }}
            .otp-box {{ background: #f4f4f5; border: 2px dashed #000000; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0; }}
            .otp-code {{ font-size: 32px; font-weight: 900; letter-spacing: 0.25em; color: #000000; font-family: monospace; }}
            .info {{ font-size: 13px; color: #52525b; line-height: 1.6; text-align: center; }}
            .footer {{ font-size: 11px; color: #a1a1aa; text-align: center; margin-top: 24px; border-top: 1px solid #f4f4f5; padding-top: 16px; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="brand">ARNA LUXURY FASHION</div>
            <p style="font-size: 15px; font-weight: 600; color: #18181b; text-align: center; margin: 0;">
              Verify Your Account
            </p>
            <p class="info" style="margin-top: 8px;">
              Please use the verification code below to complete your authentication.
            </p>
            <div class="otp-box">
              <div class="otp-code">{otp_code}</div>
            </div>
            <p class="info">
              This code is valid for <strong>10 minutes</strong>. Never share this code with anyone.
            </p>
            <div class="footer">
              &copy; 2026 ARNA Luxury Fashion Store. All rights reserved.
            </div>
          </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, "html"))

        # Send via Gmail SMTP SSL port 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())

        return {
            "delivered": True,
            "channel": "gmail_smtp",
            "message": f"Real verification email delivered to {to_email}"
        }
    except Exception as e:
        print(f"Gmail SMTP Error: {e}")
        return {
            "delivered": False,
            "channel": "error",
            "message": f"SMTP error: {str(e)}"
        }

def send_sms_otp(to_phone: str, otp_code: str) -> dict:
    """
    Send real 6-digit SMS OTP to customer's mobile phone (+91...).
    Supports Fast2SMS (India) and Twilio (Global).
    """
    clean_digits = "".join([c for c in to_phone if c.isdigit()])
    if len(clean_digits) > 10:
        clean_digits = clean_digits[-10:] # Last 10 digits for Indian numbers

    # 1. Try Fast2SMS (India)
    if FAST2SMS_API_KEY:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {"authorization": FAST2SMS_API_KEY}
            payload = {
                "variables_values": otp_code,
                "route": "otp",
                "numbers": clean_digits
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, headers=headers, data=payload)
                if res.status_code == 200:
                    return {
                        "delivered": True,
                        "channel": "fast2sms",
                        "message": f"Real SMS OTP sent to {to_phone}"
                    }
        except Exception as e:
            print(f"Fast2SMS error: {e}")

    # 2. Try Twilio (Global)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            data = {
                "From": TWILIO_PHONE_NUMBER,
                "To": to_phone if to_phone.startswith("+") else f"+91{clean_digits}",
                "Body": f"Your ARNA verification code is: {otp_code}. Valid for 10 minutes."
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, auth=auth, data=data)
                if res.status_code in (200, 201):
                    return {
                        "delivered": True,
                        "channel": "twilio",
                        "message": f"Real SMS OTP sent to {to_phone}"
                    }
        except Exception as e:
            print(f"Twilio error: {e}")

    # Fallback to simulation mode if no gateway keys are set
    return {
        "delivered": False,
        "channel": "simulation",
        "message": "SMS gateway not configured in .env. Code displayed on-screen for testing."
    }
