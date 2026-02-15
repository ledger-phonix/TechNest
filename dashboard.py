from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app, jsonify
from functools import wraps
from auth import  save_to_cloudinary
from db_manager import get_user_dashboard_data, get_detailed_profile_data, get_db_connection, with_db
import os
from chat import get_sender_details

dashboard_bp = Blueprint('dashboard', __name__)

# Security Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@dashboard_bp.route('/dashboard')
@login_required
@with_db
def index(conn): # conn is now injected by the decorator
    member_id = session.get('user_id')
    role = session.get('role')
    
    # These helpers already handle their own DB logic/connections
    user_data = get_user_dashboard_data(member_id, role)
    
    if not user_data:
        flash("Profile data not found.", "danger")
        return redirect(url_for('auth.login'))

    internal_news = []
    active_quiz = None
    
    try:
        # The decorator ensures conn is active and cursor uses DictCursor 
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT news_id, title, content, category, created_at 
                FROM news_posts 
                ORDER BY created_at DESC LIMIT 4
            """)
            internal_news = cursor.fetchall()

            cursor.execute("SELECT * FROM daily_quiz WHERE id = 1")
            active_quiz = cursor.fetchone()
            
    except Exception as e:
        print(f"Database Error in Dashboard Index: {e}")
        # We don't need to close 'conn' here; the decorator handles it

    return render_template('dashboard/index.html', 
                           member=user_data if role == 'individual' else None,
                           company=user_data if role == 'company' else None,
                           role=role, 
                           name=user_data.get('name'),
                           profile_url=user_data.get('profile_url'),
                           internal_news=internal_news,  
                           active_quiz=active_quiz)   

@dashboard_bp.route('/dashboard/profile')
@login_required
def profile():
    member_id = session.get('user_id')
    role = session.get('role')

    user_data = get_detailed_profile_data(member_id, role)
    
    if not user_data:
        flash("Could not load profile data.", "danger")
        return redirect(url_for('dashboard.index'))

    # --- CLOUD-READY IMAGE LOGIC ---
    # Fetch the value from the DB (pic_path for users, company_logo for companies)
    raw_img = user_data.get('pic_path') if role == 'individual' else user_data.get('company_logo')
    
    if raw_img and (raw_img.startswith('http://') or raw_img.startswith('https://')):
        # Case A: It's a Cloudinary URL
        profile_url = raw_img
    else:
        # Case B: No photo, generate avatar using the name
        name_for_avatar = user_data.get('first_name') if role == 'individual' else user_data.get('company_name')
        name_for_avatar = name_for_avatar or 'User'
        
        bg_color = "0d6efd" if role == 'individual' else "0D8ABC"
        profile_url = f"https://ui-avatars.com/api/?name={name_for_avatar}&background={bg_color}&color=fff"

    # --- RENDER LOGIC ---
    if role == 'individual':
        return render_template('dashboard/profile_individual.html', 
                                member=user_data, 
                                role=role, 
                                profile_url=profile_url)
    
    elif role == 'company':
        services = user_data.get('services', [])
        service_ids = ",".join([str(s['pro_id']) for s in services])

        return render_template('dashboard/profile_company.html', 
                            company=user_data, 
                            role=role, 
                            profile_url=profile_url,
                            current_services=services,
                            current_service_ids=service_ids)

    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard/profile/individual/update', methods=['POST'])
@login_required
@with_db
def update_profile_individual(conn):  # conn is injected by @with_db
    member_id = session.get('user_id')
    
    # 1. Fetch Form Data
    first_name = request.form.get('first_name', '').strip()
    second_name = request.form.get('second_name', '').strip()
    raw_pro_id = request.form.get('pro_id')
    education = request.form.get('education', '').strip()
    experience = request.form.get('experience', '').strip()
    tagline = request.form.get('tagline', '').strip()
    skills_list = request.form.get('skills_list') 

    new_pic_url = None
    new_public_id = None
    
    try:
        with conn.cursor() as cursor:
            # 2. Fetch current record (Guaranteed DictCursor via your pool setup)
            cursor.execute("""
                SELECT pic_path, profile_public_id, user_id, pro_id 
                FROM users WHERE member_id = %s
            """, (member_id,))
            user_record = cursor.fetchone()
            
            if not user_record:
                flash("User record not found.", "danger")
                return redirect(url_for('dashboard.profile'))

            # Extracting values from the dictionary result
            old_pic_path = user_record.get('pic_path')
            old_public_id = user_record.get('profile_public_id')
            internal_user_id = user_record.get('user_id')
            existing_pro_id = user_record.get('pro_id')

            # 3. Handle File Upload
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and file.filename != '':
                    # Optional: Check file size (Back-end safety)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size <= 2 * 1024 * 1024:
                        new_pic_url, new_public_id = save_to_cloudinary(file, 'profiles', member_id)

            # 4. Final Values Logic
            final_pic = new_pic_url if new_pic_url else old_pic_path
            final_p_id = new_public_id if new_public_id else old_public_id
            pro_id = int(raw_pro_id) if raw_pro_id and str(raw_pro_id).strip().isdigit() else existing_pro_id

            # 5. Update Database
            sql = """UPDATE users SET 
                        first_name=%s, second_name=%s, pro_id=%s, 
                        education=%s, experience=%s, tagline=%s, 
                        pic_path=%s, profile_public_id=%s 
                     WHERE member_id=%s"""
            cursor.execute(sql, (first_name, second_name, pro_id, education, 
                                experience, tagline, final_pic, final_p_id, member_id))

            # 6. Skills Sync (Atomic within the same transaction)
            if internal_user_id:
                cursor.execute("DELETE FROM user_skills WHERE user_id = %s", (internal_user_id,))
                if skills_list:
                    # Clean and deduplicate IDs
                    s_ids = {sid.strip() for sid in skills_list.split(',') if sid.strip().isdigit()}
                    for s_id in s_ids:
                        cursor.execute("INSERT INTO user_skills (user_id, skill_id) VALUES (%s, %s)", 
                                       (internal_user_id, int(s_id)))

            flash("Profile updated successfully!", "success")

    except Exception as e:
        print(f"Update Error: {e}")
        flash("An error occurred while saving your profile.", "danger")
        # No need for manual rollback; @with_db catches the exception and rolls back
        raise e # Re-raise to trigger the decorator's error handling

    return redirect(url_for('dashboard.profile'))

@dashboard_bp.route('/dashboard/profile/company/update', methods=['POST'])
@login_required
@with_db
def update_profile_company(conn):
    member_id = session.get('user_id')
    
    # 1. Fetch Form Data
    company_name = request.form.get('company_name', '').strip()
    owner_name = request.form.get('owner_name', '').strip()
    employee_range = request.form.get('employee_range')
    about = request.form.get('about', '').strip()
    web_url = request.form.get('web_url', '').strip()
    services_list = request.form.get('service_ids') 

    new_logo_name = None
    new_public_id = None
    
    try:
        with conn.cursor() as cursor:
            # 2. Fetch current record
            cursor.execute("""
                SELECT company_logo, logo_public_id, comp_id 
                FROM companies WHERE member_id = %s
            """, (member_id,))
            comp_record = cursor.fetchone()
            
            if not comp_record:
                flash("Company record not found.", "danger")
                return redirect(url_for('dashboard.profile'))

            # Standardized dictionary access
            old_logo_path = comp_record.get('company_logo')
            old_public_id = comp_record.get('logo_public_id')
            comp_id = comp_record.get('comp_id')

            # 3. Handle Logo Upload
            if 'company_logo' in request.files:
                file = request.files['company_logo']
                if file and file.filename != '':
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > 2 * 1024 * 1024:
                        flash("File too large. Max 2MB allowed.", "danger")
                        return redirect(url_for('dashboard.profile'))

                    new_logo_name, new_public_id = save_to_cloudinary(file, 'logos', member_id)

            # 4. Update Company Table
            final_logo = new_logo_name if new_logo_name else old_logo_path
            final_public_id = new_public_id if new_public_id else old_public_id
            
            sql = """UPDATE companies SET 
                        company_name=%s, owner_name=%s, employee_range=%s, 
                        about=%s, web_url=%s, company_logo=%s, logo_public_id=%s 
                     WHERE comp_id=%s"""
            
            cursor.execute(sql, (company_name, owner_name, employee_range, 
                                about, web_url, final_logo, final_public_id, comp_id))

            # 5. Sync Services (Atomic: if this fails, the company table update rolls back)
            cursor.execute("DELETE FROM comp_services WHERE comp_id = %s", (comp_id,))
            
            if services_list:
                s_ids = {sid.strip() for sid in services_list.split(',') if sid.strip().isdigit()}
                for s_id in s_ids:
                    cursor.execute("INSERT INTO comp_services (comp_id, pro_id) VALUES (%s, %s)", 
                                   (comp_id, int(s_id)))

            flash("Company profile updated successfully!", "success")

    except Exception as e:
        print(f"Company Update Error: {e}")
        flash("An error occurred while saving.", "danger")
        # Decorator handles the rollback automatically
        raise e

    return redirect(url_for('dashboard.profile'))

@dashboard_bp.route('/api/unread-notifications')
@login_required
@with_db
def unread_notifications(conn): # Injected by decorator
    m_id = session.get('user_id')
    role = session.get('role')
    
    try:
        with conn.cursor() as cursor:
            # 1. Get the correct numeric ID based on the role
            if role == 'company':
                cursor.execute("SELECT comp_id FROM companies WHERE member_id = %s", (m_id,))
                res = cursor.fetchone()
                # Use .get() to prevent KeyError if the record is missing
                actual_id = res.get('comp_id') if res else None
            else:
                cursor.execute("SELECT user_id FROM users WHERE member_id = %s", (m_id,))
                res = cursor.fetchone()
                actual_id = res.get('user_id') if res else None

            # 2. Return zero if no matching profile is found
            if not actual_id:
                return jsonify({'count': 0})

            # 3. Count unread notifications specific to this ID AND Role
            # This ensures total isolation between companies and individuals
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM notifications 
                WHERE user_id = %s AND user_role = %s AND is_read = 0
            """, (actual_id, role))
            
            result = cursor.fetchone()
            count_val = result.get('count') if result else 0
            
            return jsonify({'count': count_val})

    except Exception as e:
        print(f"Notification API Error: {e}")
        return jsonify({'count': 0}), 500

@dashboard_bp.route('/notifications')
@login_required
@with_db
def notifications(conn): # conn is now managed by the decorator
    m_id = session.get('user_id')
    role = session.get('role')
    
    try:
        with conn.cursor() as cursor:
            # 1. FIND THE PROPER INTEGER ID BASED ON ROLE
            if role == 'company':
                cursor.execute("SELECT comp_id FROM companies WHERE member_id = %s", (m_id,))
                res = cursor.fetchone()
                actual_id = res.get('comp_id') if res else None
            else:
                cursor.execute("SELECT user_id FROM users WHERE member_id = %s", (m_id,))
                res = cursor.fetchone()
                actual_id = res.get('user_id') if res else None

            if not actual_id:
                return redirect(url_for('dashboard.index'))

            # 2. MARK AS READ (Securely scoped to ID and Role)
            cursor.execute("""
                UPDATE notifications 
                SET is_read = TRUE 
                WHERE user_id = %s AND user_role = %s
            """, (actual_id, role))
            # No manual conn.commit() needed; @with_db handles it after function return

            # 3. FETCH NOTIFICATIONS
            if role == 'individual':
                cursor.execute("""
                    SELECT * FROM notifications 
                    WHERE user_id = %s AND user_role = 'individual' 
                    ORDER BY created_at DESC
                """, (actual_id,))
            else:
                # Filter: Companies should not see job_match notifications
                cursor.execute("""
                    SELECT * FROM notifications 
                    WHERE user_id = %s AND user_role = 'company' AND type != 'job_match' 
                    ORDER BY created_at DESC
                """, (actual_id,))
            
            all_notifs = cursor.fetchall()
            
        # Fetch layout details
        display_name, profile_url, _, _ = get_sender_details(m_id, role)
        
        return render_template('dashboard/notifications.html', 
                               notifications=all_notifs, 
                               name=display_name, 
                               profile_url=profile_url, 
                               role=role)

    except Exception as e:
        print(f"Notifications Error: {e}")
        flash("Could not load notifications.", "warning")
        return redirect(url_for('dashboard.index'))
@dashboard_bp.route('/notifications/delete-all', methods=['POST'])
@login_required
@with_db
def delete_notifications(conn): # Injected by decorator
    m_id = session.get('user_id')
    role = session.get('role')
    
    try:
        with conn.cursor() as cursor:
            # 1. FIND THE PROPER INTEGER ID BASED ON ROLE
            if role == 'company':
                cursor.execute("SELECT comp_id FROM companies WHERE member_id = %s", (m_id,))
                result = cursor.fetchone()
                actual_id = result.get('comp_id') if result else None
            else:
                cursor.execute("SELECT user_id FROM users WHERE member_id = %s", (m_id,))
                result = cursor.fetchone()
                actual_id = result.get('user_id') if result else None

            # 2. PERFORM DELETION (Scoped to ID AND Role for security)
            if actual_id:
                # Adding user_role = %s prevents deleting notifications for the wrong entity type
                cursor.execute("""
                    DELETE FROM notifications 
                    WHERE user_id = %s AND user_role = %s
                """, (actual_id, role))
                
                # No manual commit or rollback needed; @with_db handles it
                flash("Notifications cleared successfully!", "success")
            else:
                flash("Error: Profile not found.", "warning")
            
    except Exception as e:
        print(f"Delete Error: {e}")
        flash("A system error occurred while clearing notifications.", "danger")
        # Decorator will trigger rollback automatically
        
    return redirect(url_for('dashboard.notifications'))