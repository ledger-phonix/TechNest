import random
from flask_mail import Message
from flask import current_app
def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(mail, recipient_email, otp):
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(
        "Verify Your TechNest Account",
        sender=sender_email, # Fetches from app.py
        recipients=[recipient_email]
    )
    
# Replace 'YOUR_PUBLIC_LOGO_URL' with your actual Cloudinary link 
# Example: https://res.cloudinary.com/demo/image/upload/v12345/TechNest_logo1.png

    logo_url = "https://res.cloudinary.com/ducxgtmyr/image/upload/v1771140032/TechNest_favicon_uh3rlm.png" 

    msg.html = f"""
    <div style="background-color: #f4f7f9; padding: 40px 0; font-family: 'Segoe UI', Helvetica, Arial, sans-serif;">
        <div style="max-width: 550px; margin: auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e1e8ed;">
            
            <div style="background-color: #ffffff; padding: 30px; text-align: center; border-bottom: 1px solid #eef2f5;">
                <img src="{logo_url}" alt="TechNest Logo" style="width: 60px; height: auto; margin-bottom: 10px;">
                <h1 style="color: #0d6efd; margin: 0; font-size: 28px; letter-spacing: 1px;">TechNest</h1>
                <p style="color: #657786; margin: 5px 0 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; font-weight: bold;">Innovate • Connect • Build</p>
            </div>

            <div style="padding: 40px 30px;">
                <h3 style="color: #1a1f36; margin-top: 0;">Verify Your Identity</h3>
                <p style="color: #4f566b; font-size: 16px; line-height: 1.6;">
                    Welcome to the <b>TechNest Community</b>. You're one step away from connecting with fellow innovators. Use the secure code below to finalize your verification:
                </p>

                <div style="margin: 35px 0; padding: 25px; background-color: #f8fbff; border: 2px dashed #adcfff; border-radius: 8px; text-align: center;">
                    <span style="display: block; color: #657786; font-size: 12px; margin-bottom: 10px; text-transform: uppercase; font-weight: bold;">Your Verification Code</span>
                    <h1 style="margin: 0; font-size: 42px; color: #0d6efd; letter-spacing: 10px; font-family: monospace;">{otp}</h1>
                    <p style="margin: 10px 0 0 0; color: #e63946; font-size: 13px;">
                        <b>Expires in 5 minutes</b> — don't keep the community waiting!
                    </p>
                </div>

                <hr style="border: 0; border-top: 1px solid #eef2f5; margin: 30px 0;">
                <div style="color: #4f566b; font-size: 14px;">
                    <p style="margin-bottom: 5px; font-weight: bold; color: #1a1f36;">Why TechNest?</p>
                    <ul style="padding-left: 20px; margin: 0; line-height: 1.5;">
                        <li>Real-time community chat & collaboration.</li>
                        <li>Exclusive tech insights and file sharing.</li>
                        <li>Networking with verified industry professionals.</li>
                    </ul>
                </div>
            </div>

            <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #eef2f5;">
                <p style="margin: 0; font-size: 12px; color: #aab8c2;">
                    This is an automated security message from TechNest Community.<br>
                    If you did not request this code, please ignore this email or contact support.
                </p>
            </div>
        </div>
    </div>
    """
    mail.send(msg)