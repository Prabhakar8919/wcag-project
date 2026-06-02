import secrets
import logging
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.hashers import make_password, check_password

logger = logging.getLogger(__name__)

def generate_otp_code() -> str:
    """
    Generates a secure, cryptographically random 6-digit numeric OTP string.
    """
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(6))

def send_otp_email(user, raw_otp: str, action: str = "verify") -> bool:
    """
    Sends a beautifully designed HTML OTP verification email to the user.
    Integrates Django SMTP backend with a seamless local console print fallback
    to prevent system crashes if credentials are not configured in .env.
    """
    user_name = user.first_name if user.first_name else user.username
    
    if action == "login":
        subject = f"{raw_otp} is your WCAG Auditor Login Code"
        welcome_title = "Account Login Verification"
        message_body = f"We received a request to log in to your WCAG Auditor AI account. Hello {user_name}, to complete your authentication process, please enter the 6-digit verification code below."
    else:
        subject = f"{raw_otp} is your WCAG Auditor Verification Code"
        welcome_title = "Verify Your Email Address"
        message_body = f"Thank you for signing up for WCAG Auditor AI, {user_name}. To complete your account activation and access your premium accessibility auditing tools, please enter the 6-digit verification code below."

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@wcagauditor.com')
    to_email = user.email

    # HTML Email Template Content aligned with premium SaaS branding
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Inter', -apple-system, sans-serif;
                background-color: #050816;
                color: #E2E8F0;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background: #0f172a;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            }}
            .header {{
                text-align: center;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .logo-text {{
                font-size: 24px;
                font-weight: 700;
                color: #FFFFFF;
            }}
            .logo-highlight {{
                color: #00D9FF;
            }}
            .welcome {{
                font-size: 18px;
                font-weight: 600;
                color: #FFFFFF;
                margin-bottom: 16px;
            }}
            .message {{
                font-size: 14px;
                line-height: 1.6;
                color: #94A3B8;
                margin-bottom: 30px;
            }}
            .otp-container {{
                background: #020617;
                border: 1px solid rgba(0, 217, 255, 0.15);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                margin: 30px 0;
                box-shadow: inset 0 0 20px rgba(0, 217, 255, 0.05);
            }}
            .otp-code {{
                font-family: 'Space Grotesk', monospace;
                font-size: 36px;
                font-weight: 700;
                color: #00D9FF;
                letter-spacing: 8px;
                text-shadow: 0 0 15px rgba(0, 217, 255, 0.4);
                margin: 0;
            }}
            .expiry-warning {{
                font-size: 12px;
                color: #EC4899;
                font-weight: 600;
                margin-top: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .footer {{
                text-align: center;
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                padding-top: 20px;
                margin-top: 40px;
                font-size: 11px;
                color: #64748B;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo-text">WCAG <span class="logo-highlight">Auditor AI</span></div>
            </div>
            
            <div class="welcome">{welcome_title}</div>
            
            <div class="message">
                {message_body}
            </div>
            
            <div class="otp-container">
                <div class="otp-code">{raw_otp}</div>
                <div class="expiry-warning">⚠️ Code expires in 10 minutes</div>
            </div>
            
            <div class="message" style="margin-top: 20px;">
                If you did not initiate this request or register an account with us, you can safely ignore this email. Your security is our priority.
            </div>
            
            <div class="footer">
                &copy; 2026 WCAG Auditor AI. All rights reserved.<br>
                Enterprise SaaS Accessibility Verification Protocol
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"Welcome to WCAG Auditor AI! Your 6-digit verification code is: {raw_otp}. Note: This code expires in 10 minutes."

    # Validate if Gmail SMTP credentials are set
    smtp_ready = (
        getattr(settings, 'EMAIL_HOST_USER', None) and 
        getattr(settings, 'EMAIL_HOST_PASSWORD', None) and
        settings.EMAIL_HOST_USER != 'your-email@gmail.com'
    )

    if smtp_ready:
        try:
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            logger.info(f"OTP Email sent successfully via SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"SMTP Failed: {e}. Falling back to Console presentation.")
            
    # Premium Local Fallback presentation in console so development does not crash!
    print("=" * 70)
    print(f"[OTP] [WCAG AUDITOR - OTP EMAIL {action.upper()} VERIFICATION LOG]")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Verification Code: {raw_otp}")
    print("Expires in: 10 Minutes")
    if not smtp_ready:
        print("NOTE: Gmail SMTP credentials are not configured in your .env. Using console fallback.")
    print("=" * 70)

    return True

def send_otp_email_async(user, raw_otp: str, action: str = "verify"):
    """
    Asynchronously sends the OTP email via a daemonized background Thread.
    Ensures that the HTTP response is returned immediately to the client
    without waiting for SMTP roundtrip latency.
    """
    import threading
    thread = threading.Thread(target=send_otp_email, args=(user, raw_otp, action))
    thread.daemon = True
    thread.start()

def send_welcome_email(user) -> bool:
    """
    Sends a beautifully designed HTML Welcome email to the user upon successful activation.
    """
    subject = "Welcome to WCAG Auditor AI! 🎉"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@wcagauditor.com')
    to_email = user.email
    user_name = user.first_name if user.first_name else user.username
    login_url = "http://54.79.186.199:8000/login/"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Inter', -apple-system, sans-serif;
                background-color: #050816;
                color: #E2E8F0;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background: #0f172a;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            }}
            .header {{
                text-align: center;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .logo-text {{
                font-size: 24px;
                font-weight: 700;
                color: #FFFFFF;
            }}
            .logo-highlight {{
                color: #00D9FF;
            }}
            .welcome {{
                font-size: 20px;
                font-weight: 700;
                color: #00D9FF;
                margin-bottom: 16px;
                text-align: center;
            }}
            .message {{
                font-size: 14px;
                line-height: 1.6;
                color: #94A3B8;
                margin-bottom: 20px;
            }}
            .action-box {{
                background: #020617;
                border: 1px solid rgba(139, 92, 246, 0.2);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                margin: 30px 0;
            }}
            .btn-welcome {{
                display: inline-block;
                padding: 12px 24px;
                background: linear-gradient(135deg, #00D9FF, #8B5CF6);
                color: #FFFFFF !important;
                font-weight: 700;
                text-decoration: none;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3);
            }}
            .footer {{
                text-align: center;
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                padding-top: 20px;
                margin-top: 40px;
                font-size: 11px;
                color: #64748B;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo-text">WCAG <span class="logo-highlight">Auditor AI</span></div>
            </div>
            
            <div class="welcome">Welcome to WCAG Auditor AI! 🎉</div>
            
            <div class="message">
                Hello {user_name},
            </div>
            
            <div class="message">
                Your email address has been successfully verified! Your new secure accessibility scanning account is now fully active.
            </div>
            
            <div class="message">
                WCAG Auditor AI provides you with enterprise-grade web crawlers, real-time visual inspection overlays, and automated semantic usability intelligence powered by Groq Llama 3.1 modeling.
            </div>
            
            <div class="action-box">
                <p style="color: #FFFFFF; font-weight: 600; margin-bottom: 16px; font-size: 14px;">Ready to audit your first website?</p>
                <a href="{login_url}" class="btn-welcome">Launch Scanner Console</a>
            </div>
            
            <div class="footer">
                &copy; 2026 WCAG Auditor AI. All rights reserved.<br>
                Enterprise SaaS Accessibility Verification Protocol
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"Welcome to WCAG Auditor AI, {user_name}! Your account is verified. Launch your scanner console at {login_url}"

    smtp_ready = (
        getattr(settings, 'EMAIL_HOST_USER', None) and 
        getattr(settings, 'EMAIL_HOST_PASSWORD', None) and
        settings.EMAIL_HOST_USER != 'your-email@gmail.com'
    )

    if smtp_ready:
        try:
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            logger.info(f"Welcome Email sent successfully via SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"SMTP Welcome Email Failed: {e}. Falling back to Console log.")

    # Fallback to Console log
    print("=" * 70)
    print("[WELCOME] [WCAG AUDITOR - WELCOME EMAIL LOG]")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Welcome Message sent to: {user_name}")
    print("=" * 70)
    
    return True

def send_welcome_email_async(user):
    """
    Asynchronously sends the welcome email via a background Thread.
    """
    import threading
    thread = threading.Thread(target=send_welcome_email, args=(user,))
    thread.daemon = True
    thread.start()

def setup_user_otp(profile) -> str:
    """
    Generates a secure 6-digit OTP, saves its PBKDF2 hash on the user profile,
    sets a 10-minute expiry time, and resets the attempt counter.
    Returns the raw OTP string so it can be sent via email.
    """
    raw_otp = generate_otp_code()
    
    # Secure hashed storage using Django native pass hashers
    profile.otp_code = make_password(raw_otp)
    profile.otp_created_at = timezone.now()
    profile.otp_expiry = timezone.now() + timedelta(minutes=10)
    profile.otp_attempts = 0
    profile.save()
    
    return raw_otp

def verify_otp_code(profile, raw_otp: str, require_existing_verification: bool = False) -> tuple[bool, str]:
    """
    Verifies the provided 6-digit OTP code against the hashed storage on the profile.
    Enforces expiration limits, attempt limits (brute-force lockout), and invalid codes.

    For users that are already email-verified, a login OTP still requires checking the
    submitted code when require_existing_verification=True.

    Returns: (success_boolean, feedback_message)
    """
    if profile.is_email_verified and not require_existing_verification:
        return True, "Email is already verified."
        
    if not profile.otp_code or not profile.otp_expiry:
        return False, "No active verification code found. Please request a new one."
        
    # 1. Brute-force Lockout check (Max 5 attempts)
    if profile.otp_attempts >= 5:
        # Invalidate code
        profile.otp_code = None
        profile.save()
        return False, "Too many failed attempts. This code has been locked. Please request a new one."
        
    # 2. Expiration Validation
    if timezone.now() > profile.otp_expiry:
        return False, "This verification code has expired. Please request a new one."
        
    # 3. Code Verification
    if check_password(raw_otp, profile.otp_code):
        message = "Email verified successfully!" if not profile.is_email_verified else "Verification successful."
        if not profile.is_email_verified:
            profile.is_email_verified = True
        profile.otp_code = None
        profile.otp_expiry = None
        profile.otp_attempts = 0
        profile.save()
        return True, message
    else:
        profile.otp_attempts += 1
        profile.save()
        remaining = 5 - profile.otp_attempts
        if remaining <= 0:
            profile.otp_code = None
            profile.save()
            return False, "Incorrect code. Too many failed attempts. Code locked out."
        return False, f"Incorrect verification code. {remaining} attempts remaining."
