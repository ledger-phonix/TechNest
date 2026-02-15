from flask import Flask, render_template, request, redirect, url_for, flash, session
from mail_service import generate_otp, send_otp_email # Import your utilities
from db_manager import get_all_members, get_all_companies, get_companies_count, get_members_count, get_detailed_profile_data, get_public_jobs, get_jobs_count
from flask_mail import Mail, Message
from members import members_bp
from companies import companies_bp
import os
from dotenv import load_dotenv
from flask_socketio import SocketIO
from chat import chat_bp, init_chat_socket, cleanup_old_chats
from auth import auth_bp
from datetime import datetime, timedelta
import time
from dashboard import dashboard_bp
import threading
from jobs import jobs_bp
from admin_routes import admin_bp
import cloudinary
# Inside your app setup

load_dotenv()
# Register the blueprints


app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY')  # Required for flashing messages later
# Configuration for Flask-Mail
# Set maximum content length to 10MB + a bit of buffer for form data
#----------Cloud file uplaoding system-----------------
# Configuration - This pulls from your CLOUDINARY_URL in .env
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key = os.getenv('CLOUDINARY_API_KEY'),
    api_secret = os.getenv('CLOUDINARY_API_SECRET'),
    secure = True
)
app.config['MAX_CONTENT_LENGTH'] = 11 * 1024 * 1024 

# Force cookies to be sent over HTTPS only
app.config['SESSION_COOKIE_SECURE'] = True 
# Prevent JavaScript from reading the session cookie
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Prevent CSRF (Cross-Site Request Forgery) attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME') 
# This tells Flask to always use your Gmail as the "From" address
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

socketio = SocketIO(app)

# Register the Blueprint for routes
app.register_blueprint(chat_bp)
app.register_blueprint(members_bp)
app.register_blueprint(companies_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(admin_bp)
# Register the Socket events
init_chat_socket(socketio)
mail = Mail(app)
# 1. Home Page
@app.route('/')
def home():
    return render_template('main/home.html')

# 2. About Us Page
@app.route('/about')
def about():
    return render_template('main/about.html')

# 3. Contact Us Page
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # 1. Capture data from HTML 'name' attributes
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # 2. Create the Email Message
        msg = Message(
            subject=f"TechNest: {subject}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[os.getenv('MAIL_RECEIVER')],
            body=f"From: {name} <{email}>\n\nMessage:\n{message}"
        )

        # 3. Try to send
        try:
            mail.send(msg)
            flash("Success! Your message has been sent.", "success")
        except Exception as e:
            print(f"Mail Error: {e}")
            flash("Error: Could not send email. Check your configuration.", "danger")

        return redirect(url_for('contact'))

    return render_template('main/contact.html')


app.register_blueprint(auth_bp)
@app.route('/signup', methods=['GET', 'POST']) # Must allow POST
def signup():
    if request.method == 'POST':
        # 1. Collect form data
        email = request.form.get('email')

        from db_manager import is_email_registered
        if is_email_registered(email):
            flash("This email is already registered. Please login.", "warning")
            return redirect(url_for('login'))
        
        # 2. Store user data in session (to save to DB LATER after OTP)
       
        session['temp_user_data'] = request.form 
        session['temp_user_email'] = email # Used by your resend_otp logic
        
        # 3. Generate and store OTP professionally
        otp = generate_otp()
        session['otp'] = otp
        session['otp_expiry'] = (datetime.now() + timedelta(minutes=5)).timestamp()
        session['resend_count'] = 0
        
        # 4. Send the Email
        try:
            send_otp_email(mail, email, otp)
            return redirect(url_for('auth.verify_otp')) # Redirect to Blueprint route
        except Exception as e:
            print(f"Mail Error: {e}")
            flash("Error sending email. Please try again.", "danger")
            
    return render_template('auth/signup.html')

# 5. Login Page
@app.route('/login')
def login():
    return render_template('auth/login.html')

# 6. FAQ Page
@app.route('/faq')
def faq():
    return render_template('legal/faq.html')

# 7. Privacy Policy Page
@app.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')

# 8. Guidlines Page
@app.route('/guidelines')
def guidelines():
    return render_template('legal/guidelines.html')

app.register_blueprint(dashboard_bp) # Add this line
@app.route('/members')
def members():
    members_list = []
    total_count = 0
    try:
        limit = 20 # Remember to set this to 1 for your test!
        members_list = get_all_members(limit=limit, offset=0)
        # ADD THIS PRINT LINE
       
        total_count = get_members_count()
        # print(f"DEBUG: Members List Count: {len(members_list)} | Total Count: {total_count}")
        return render_template('main/members.html', 
                               members=members_list, 
                               total_count=total_count)
    except Exception as e:
        print(f"Members Route Error: {e}")
        return render_template('main/members.html', members=[], total_count=0)

@app.route('/load-more-members')
def load_more_members():
    offset = int(request.args.get('offset', 0))
    limit = 20 # Match your main route limit
    members_list = get_all_members(limit=limit, offset=offset)
    return render_template('partials/_member_card.html', members=members_list)

@app.route('/companies')
def companies():
    try:
        limit = 20
        companies_list = get_all_companies(limit=limit, offset=0)
        total_count = get_companies_count()
        return render_template('main/companies.html', 
                               companies=companies_list, 
                               total_count=total_count)
    except Exception as e:
        print(f"Route Error: {e}")
        # ALWAYS pass total_count=0 so the template/JS doesn't break
        return render_template('main/companies.html', companies=[], total_count=0)
    
@app.route('/load-more-companies')
def load_more():
    offset = int(request.args.get('offset', 0))
    limit = 20
    companies_list = get_all_companies(limit=limit, offset=offset)
    # We render ONLY the partial file, not the whole page!
    return render_template('partials/_company_card.html', companies=companies_list)

@app.route('/jobs')
def jobs():
    try:
        limit = 20
        # Call the manager functions
        jobs_list = get_public_jobs(limit=limit, offset=0)
        total_count = get_jobs_count()
        
        return render_template('main/jobs.html', 
                               jobs=jobs_list, 
                               total_count=total_count)
    except Exception as e:
        print(f"Route Error: {e}")
        # Return empty list and 0 count to keep template safe
        return render_template('main/jobs.html', jobs=[], total_count=0)
    
@app.route('/load-more-jobs')
def load_more_jobs():
    offset = int(request.args.get('offset', 0))
    limit = 20
    # Use your existing manager function
    jobs_list = get_public_jobs(limit=limit, offset=offset)
    
    # Render ONLY the individual job cards partial
    return render_template('partials/_job_card.html', jobs=jobs_list)

 # 3. Create a background task that runs every hour
def start_cleanup_scheduler(app):
    def run_loop():
        while True:
            cleanup_old_chats(app)
            time.sleep(3600) # Wait 1 hour (3600 seconds) before checking again
           
            
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()    
       
@app.route('/profile/<role>/<member_id>')
def view_member_profile(role, member_id):
    # This calls your backbone function
    member_data = get_detailed_profile_data(member_id, role)
    
    if not member_data:
        # If backbone returns None, handle it safely
        return "Member not found", 404 

    # If backbone returns data, show the profile
    return render_template('dashboard/member_profile.html', member=member_data, role=role)

from functools import wraps
# from flask import session, redirect, url_for, flash

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # We check for a specific admin_id to keep it separate from users
        if 'admin_id' not in session:
            flash("Unauthorized access. Please log in.", "danger")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function
from werkzeug.security import check_password_hash
from db_manager import get_db_connection

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Fetch only the admin with this username
                sql = "SELECT id, username, password_hash FROM admins WHERE username = %s"
                cursor.execute(sql, (username,))
                admin = cursor.fetchone() # returns a dictionary if you configured your cursor that way
                
                # admin[2] if using default cursor, admin['password_hash'] if using DictCursor
                if admin and check_password_hash(admin['password_hash'], password):
                    session['admin_id'] = admin['id']
                    session['admin_name'] = admin['username']
                    flash(f"Welcome to the cockpit, {admin['username']}", "success")
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash("Invalid credentials.", "danger")
        finally:
            conn.close()
            
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear() # Clears admin session
    return redirect(url_for('admin_login'))
@app.errorhandler(401)
def session_expired_handler(e):
    # This renders the clean page we discussed earlier
    return render_template('legal/session_timeout.html'), 401
# Run the application
if __name__ == '__main__':
    # 1. Start the 'Janitor' thread FIRST
    # We start this before the server so it's ready to work
    start_cleanup_scheduler(app) 
    DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    # 2. Start the SocketIO server
    # socketio.run handles EVERYTHING (both standard routes and chat)
    # We use host='0.0.0.0' to allow network access if needed
    socketio.run(app, host='0.0.0.0', port=5001, debug=DEBUG_MODE)