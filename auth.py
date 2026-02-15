from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from datetime import datetime, timedelta
from mail_service import send_otp_email, generate_otp
from db_manager import search_suggestions
import uuid
from werkzeug.security import generate_password_hash
from db_manager import save_individual_transaction, save_company_transaction, get_user_for_login
from flask_mail import Message


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        stored_otp = session.get('otp')
        expiry_timestamp = session.get('otp_expiry')

        # Check if OTP exists and is not expired
        if not stored_otp or not expiry_timestamp:
            flash("Session expired. Please sign up again.", "danger")
            return redirect(url_for('signup'))

        if datetime.now().timestamp() > expiry_timestamp:
            flash("OTP has expired (5 min limit). Please resend.", "danger")
            return redirect(url_for('auth.verify_otp'))

        if user_otp == stored_otp:
            # Logic to save user to MySQL goes here later
            session['email_verified'] = True
           
            flash("Email verified! Welcome to TechNest.", "success")
            # 2. Get user data from session
            user_data = session.get('temp_user_data')
            role = user_data.get('role') if user_data else 'individual'
            # 3. Clean up OTP data but KEEP temp_user_data for the next form
            session.pop('otp', None)
            session.pop('otp_expiry', None)
            # 4. Redirect based on role
            if role == 'company':
                return redirect(url_for('auth.company_form'))
            else:
                return redirect(url_for('auth.individual_form'))
        else:
            flash("Invalid code. Please check your email and try again.", "danger")

    return render_template('auth/verify_otp.html')

@auth_bp.route('/resend-otp')
def resend_otp():
    # Check resend limit
    resend_count = session.get('resend_count', 0)
    if resend_count >= 2:
        flash("Resend limit reached. Please contact support or try later.", "danger")
        return redirect(url_for('auth.verify_otp'))

    # Generate new OTP
    email = session.get('temp_user_email')
    if not email:
        return redirect(url_for('signup'))

    new_otp = generate_otp()
    session['otp'] = new_otp
    session['otp_expiry'] = (datetime.now() + timedelta(minutes=5)).timestamp()
    session['resend_count'] = resend_count + 1

  
    from flask import current_app
    mail = current_app.extensions.get('mail')
    send_otp_email(mail, email, new_otp)
    
    flash(f"New code sent to {email}. (Attempt {session['resend_count']}/2)", "info")
    return redirect(url_for('auth.verify_otp'))


# --- Helper: Generate Unique Member ID ---
def generate_member_id(prefix):
    """Generates ID like IND-7F3A92"""
    unique_hex = uuid.uuid4().hex[:6].lower()
    return f"{prefix}-{unique_hex}"

import io
import cloudinary.uploader

def save_to_cloudinary(file_obj, subfolder, member_id=None):
    """
    Robust upload that reads file into memory to prevent 0-byte/corrupt uploads.
    """
    if not file_obj:
        return None, None

    try:
        # 1. CRITICAL: Read the file into memory explicitly.
        # This decouples it from the Flask request stream and prevents "pointer" errors.
        file_obj.seek(0)
        file_data = file_obj.read()
        
        # Safety Check: Did we actually get data?
        if len(file_data) == 0:
            print("!!! ERROR: File is empty (0 bytes).")
            return None, None

        # 2. Setup Folder Logic (Simplified)
        if subfolder == 'chat':
            folder = "technest/uploads/chat_files"
            public_id = None   # Random ID for chat to prevent collisions
            overwrite = False
        else:
            folder = f"technest/uploads/{subfolder}"
            public_id = str(member_id) # Force string
            overwrite = True   # Overwrite for profiles/logos

        # 3. UPLOAD using io.BytesIO
        # We wrap 'file_data' in BytesIO so it acts like a fresh new file
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(file_data), 
            folder=folder,
            public_id=public_id,
            overwrite=overwrite,
            resource_type="auto", # 'auto' handles PDF, JPG, PNG correctly
            filename=file_obj.filename # Helps Cloudinary detect MIME type
        )

        return upload_result['secure_url'], upload_result['public_id']

    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None, None

# ========================================================
# 1. INDIVIDUAL PROFILE ROUTE
# ========================================================
@auth_bp.route('/save-individual-profile', methods=['GET', 'POST'])
def individual_form():
    # Security: Ensure user came from Signup Step 1
    if 'temp_user_data' not in session:
        flash("Session expired. Please start over.", "danger")
        return redirect(url_for('signup'))

    if request.method == 'POST':
        try:
            # 1. Prepare Authentication Data
            temp_data = session['temp_user_data']
            member_id = generate_member_id("ind")
            
            auth_data = {
                'member_id': member_id,
                'email': temp_data['email'],
                # Encrypt password NOW, before saving
                'password_hash': generate_password_hash(temp_data['password']) 
            }

           # --- Cloudinary Upload Logic ---
            pic_url = None
            pic_public_id = None
            file = request.files.get('profile_pic')

            if file and file.filename != '':
                # Upload to Cloudinary using member_id as the Public ID
                pic_url, pic_public_id = save_to_cloudinary(file, 'profiles', member_id)
            # 1. Get the text from the form
            about_text = request.form.get('about', '')[:200]
    
            # 2. The Backend Safety Net: Slice to 200 characters
            # about_text = about_text[:200]
            # 3. Prepare User Profile Data
            user_data = {
                'first_name': request.form.get('first_name'),
                'second_name': request.form.get('second_name'),
                'gender': request.form.get('gender'),
                'phone_no': "+92" + request.form.get('phone_no'),
                'city': request.form.get('city'),
                'dob': request.form.get('dob'), # HTML date input returns YYYY-MM-DD
                'education': request.form.get('education'),  # NEW
                'experience': request.form.get('experience'), # NEW
                'pro_id': request.form.get('pro_id'), # Hidden input
                'tagline': request.form.get('tagline'),
                'pic_path': pic_url,
                'public_id': pic_public_id,
                'linkedin': request.form.get('linkedin_link'),
                'other_link': request.form.get('other_link')
            }

            # 4. Parse Skills List (String "1,2,3" -> List [1, 2, 3])
            skills_str = request.form.get('skills_list', '')
            skill_ids = [s for s in skills_str.split(',') if s]

            # 5. COMMIT TO DATABASE (Atomic Transaction)
            if save_individual_transaction(auth_data, user_data, skill_ids):
                # Success! Clean up session
                session.pop('temp_user_data', None)
                flash("Account created successfully! Please login.", "success")
                return redirect(url_for('login')) # Make sure you have a login route
            else:
                flash("Database error occurred. Please try again.", "danger")

        except Exception as e:
            print(f"Error in Individual Route: {e}")
            flash("Something went wrong.", "danger")

    return render_template('auth/form_individual.html')

# ========================================================
# 2. COMPANY PROFILE ROUTE
# ========================================================
@auth_bp.route('/save-company-profile', methods=['GET', 'POST'])
def company_form():
    if 'temp_user_data' not in session:
        flash("Session expired.", "danger")
        return redirect(url_for('signup'))

    if request.method == 'POST':
        try:
            # 1. Prepare Auth Data
            temp_data = session['temp_user_data']
            member_id = generate_member_id("com")

            auth_data = {
                'member_id': member_id,
                'email': temp_data['email'],
                'password_hash': generate_password_hash(temp_data['password'])
            }

            # 2. Handle Cloudinary Upload (Logo)
            logo_url = None
            logo_public_id = None
            file = request.files.get('company_logo')
            
            if file and file.filename != '':
                # Subfolder is 'logos', using member_id as the filename
                logo_url, logo_public_id = save_to_cloudinary(file, 'logos', member_id)

            about_text = request.form.get('about', '')[:200]
            # 3. Prepare Company Data
            comp_data = {
                'company_name': temp_data.get('company_name'), # Assuming fname held company name in step 1
                'owner_name': request.form.get('owner_name'),
                'est_year': request.form.get('established_year'),
                'emp_range': request.form.get('employee_range'),
                'city': request.form.get('city'),
                'address': request.form.get('address'),
                'map_url': request.form.get('google_map_url'),
                'about': request.form.get('about'),
                'logo_path': logo_url,
                'public_id': logo_public_id,
                'web_url': request.form.get('web_url'),
                'linkedin': request.form.get('linkedin_url'),
                'contact_no': "+92" + request.form.get('contact_no'),
                
            }
            
            
            # 4. Parse Services List
            services_str = request.form.get('service_ids', '')
            service_ids = [s for s in services_str.split(',') if s]

            # 5. COMMIT TO DATABASE
            if save_company_transaction(auth_data, comp_data, service_ids):
                session.pop('temp_user_data', None)
                flash("Company profile created! Please login.", "success")
                return redirect(url_for('login'))
            else:
                flash("Database error. Please try again.", "danger")

        except Exception as e:
            print(f"Error in Company Route: {e}")
            flash("An error occurred.", "danger")

    return render_template('auth/form_company.html')

# script for skills and prfession suggessions
@auth_bp.route('/api/get-suggestions')
def get_suggestions():
    try:
        search_type = request.args.get('type') 
        query = request.args.get('q', '')
        
        # print(f"--- API TRIGGERED --- Type: {search_type}, Query: {query}")

        table_config = {
            'profession': {
                'table': 'profession', 
                'id_col': 'pro_id', 
                'name_col': 'pro_name'
            },
            'skills': {
                'table': 'skills_list', 
                'id_col': 'skill_id', 
                'name_col': 'skill_name'
            },
            # NEW: Mapping 'services' to the profession table for companies
            'services': {
                'table': 'profession', 
                'id_col': 'pro_id', 
                'name_col': 'pro_name'
            }
        }
        
        config = table_config.get(search_type)
        if not config:
            print(f"Error: Type '{search_type}' not found in mapping.")
            return jsonify([])

        
        # print(f"Calling DB Manager for table: {config['table']}")
        
        results = search_suggestions(
            config['table'], 
            config['id_col'], 
            config['name_col'], 
            query
        )
        
        # print(f"DB Results Found: {len(results)}")
        return jsonify(results)

    except Exception as e:
        print(f"!!! CRITICAL ROUTE ERROR !!!: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
# Error handlers

from werkzeug.security import check_password_hash

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # NEW: Check if user is already logged in
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        # 1. Fetch user from DB
        user = get_user_for_login(email)

        # 2. Verify existence and password
        if user and check_password_hash(user['password_hash'], password):
            # SUCCESS! Create Session
            session.clear() # Wipe any temp signup data
            session['user_id'] = user['member_id']
            session['role'] = user['role']
            session['logged_in'] = True
            # --- REMEMBER ME LOGIC ---
            if remember:
                # This makes the cookie stay even after the browser closes
                session.permanent = True
                # Set how long the 'Remember Me' lasts (e.g., 30 days)
                current_app.permanent_session_lifetime = timedelta(days=30)
            else:
                # Session will expire when browser closes
                session.permanent = False
            # -------------------------
            flash("Successfully logged in!", "success")

            # 3. Redirect based on role
            if user['role'] == 'company':
                return redirect(url_for('dashboard.index')) # Replace with your actual route
            else:
                return redirect(url_for('dashboard.index')) # Replace with your actual route
        
        else:
            # FAILURE
            flash("Invalid email or password. Please try again.", "danger")

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# reseting passwords


def send_reset_email(user_email, reset_url):
    # Access the mail instance from the current app extensions
    mail = current_app.extensions.get('mail')
    
    if not mail:
        print("Error: Mail extension not initialized.")
        return False

    msg = Message('Password Reset Request - TechNest',
                  recipients=[user_email])
    
    # render_template works here as well
    msg.html = render_template('emails/reset_email.html', reset_url=reset_url)
    
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False
import secrets # Needed for generating the token

from db_manager import save_reset_token, verify_reset_token, update_password_and_clear_token, get_user_for_login

# 1. This route shows the "I forgot my password" page and sends the email
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = get_user_for_login(email) # Checks if the email exists

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(hours=1)
            
            # Use the functions you added to db_manager
            save_reset_token(email, token, expiry)
            
            # Generate the link (the _external=True makes it a full http:// link)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Use the function you added to auth.py
            send_reset_email(email, reset_url)
        
        # We flash the same message whether the email exists or not for security
        flash("If this email is registered, a reset link has been sent.", "info")
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')

# 2. This route is where the user lands when they click the link in their email
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Use your verify function
    user_data = verify_reset_token(token)
    
    if not user_data:
        flash("The reset link is invalid or has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        hashed_password = generate_password_hash(new_password)
        
        # Use your update function
        update_password_and_clear_token(user_data['email'], hashed_password)
        
        flash("Your password has been updated! You can now log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_form.html', token=token)


