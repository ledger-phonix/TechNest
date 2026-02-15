from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import check_password_hash
from db_manager import with_db
from functools import wraps


# 1. Define the Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 2. Move your Decorator here
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("Unauthorized access.", "danger")
            return redirect(url_for('admin.login')) # Note the 'admin.' prefix
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
@with_db
def login(conn): # conn is injected by @with_db
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            with conn.cursor() as cursor:
                # Query the dedicated admins table
                cursor.execute("SELECT id, username, password_hash FROM admins WHERE username = %s", (username,))
                admin = cursor.fetchone()
                
                if admin and check_password_hash(admin['password_hash'], password):
                    # Clear any existing session to prevent session fixation
                    session.clear() 
                    
                    session['admin_id'] = admin['id']
                    session['admin_name'] = admin['username']
                    
                    
                    return redirect(url_for('admin.dashboard'))
                
                flash("Invalid credentials.", "danger")
        except Exception as e:
            # Log the specific error server-side, show generic error to user
            print(f"Admin Login Error: {e}")
            flash("A system error occurred. Please try again later.", "danger")
            
    return render_template('admin/login.html')

# Make sure you've imported admin_bp and admin_required at the top of the file

@admin_bp.route('/dashboard')
@admin_required
@with_db
def dashboard(conn):  # conn is injected by @with_db
    # Default stats to zero in case of DB issues
    stats = {
        'users': 0,
        'companies': 0,
        'jobs': 0
    }
    categories = []
    
    try:
        with conn.cursor() as cursor:
            # 1. Count Total Individuals
            cursor.execute("SELECT COUNT(*) AS total FROM users")
            result_users = cursor.fetchone()
            stats['users'] = result_users['total'] if result_users else 0
            
            # 2. Count Total Companies
            cursor.execute("SELECT COUNT(*) AS total FROM companies")
            result_companies = cursor.fetchone()
            stats['companies'] = result_companies['total'] if result_companies else 0
            
            # 3. Count Active Jobs
            cursor.execute("""
                SELECT COUNT(*) AS total FROM jobs 
                WHERE expires_at >= CURDATE() OR expires_at IS NULL
            """)
            result_jobs = cursor.fetchone()
            stats['jobs'] = result_jobs['total'] if result_jobs else 0
            
            # 4. Fetch Categories
            cursor.execute("SELECT * FROM profession_category ORDER BY category_name")
            categories = cursor.fetchall()

    except Exception as e:
        # Security: Log the specific error server-side, show generic message to admin
        print(f"Admin Dashboard Stats Error: {e}")
        flash("An error occurred while loading dashboard statistics.", "danger")
        
    return render_template('admin/dashboard.html', 
                           stats=stats, 
                           categories=categories)
    
@admin_bp.route('/add-profession', methods=['POST'])
@admin_required
@with_db
def add_profession(conn): # conn is injected by @with_db
    pro_name = request.form.get('pro_name', '').strip()
    category_id = request.form.get('category_id')
    
    if pro_name and category_id:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO profession (pro_name, category_id) VALUES (%s, %s)", 
                    (pro_name, category_id)
                )
                # conn.commit() is handled automatically by @with_db on success
                flash(f"Profession '{pro_name}' added successfully!", "success")
        except Exception as e:
            print(f"Add Profession Error: {e}")
            flash("Error: This profession might already exist or the category is invalid.", "danger")
            
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/add-skill', methods=['POST'])
@admin_required
@with_db
def add_skill(conn): # conn is injected by @with_db
    skill_name = request.form.get('skill_name', '').strip()
    
    if skill_name:
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO skills_list (skill_name) VALUES (%s)", (skill_name,))
                # conn.commit() is handled automatically by @with_db on success
                flash(f"Skill '{skill_name}' added successfully!", "success")
        except Exception as e:
            print(f"Add Skill Error: {e}")
            flash("Error: This skill might already exist.", "danger")
            
    return redirect(url_for('admin.dashboard'))
@admin_bp.route('/individuals')
@admin_required
@with_db
def manage_individuals(conn): # conn is injected by @with_db
    users = []
    try:
        with conn.cursor() as cursor:
            # Joining users (u) and auth (a) on member_id
            sql = """
                SELECT 
                    u.user_id, 
                    u.member_id, 
                    u.first_name, 
                    u.second_name, 
                    u.email, 
                    a.created_at 
                FROM users u
                JOIN auth a ON u.member_id = a.member_id
                ORDER BY a.created_at DESC
            """
            cursor.execute(sql)
            users = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching individuals: {e}")
        flash("Could not retrieve user list.", "danger")
        
    return render_template('admin/individuals.html', users=users)


@admin_bp.route('/delete-user/<int:user_id>', methods=['POST']) # Changed to POST for security
@admin_required
@with_db
def delete_user(conn, user_id): # conn is injected by @with_db
    try:
        with conn.cursor() as cursor:
            # 1. Fetch member_id and Cloudinary ID BEFORE deleting from DB
            cursor.execute("""
                SELECT member_id, profile_public_id 
                FROM users 
                WHERE user_id = %s
            """, (user_id,))
            user_data = cursor.fetchone()

            if not user_data:
                flash("User not found.", "danger")
                return redirect(url_for('admin.manage_individuals'))

            # 2. Handle Cloudinary Cleanup
            public_id = user_data.get('profile_public_id')
            if public_id:
                import cloudinary.uploader
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception as c_error:
                    # Log but continue; DB integrity is higher priority
                    print(f"Cloudinary Orphaned File Alert: {c_error}")

            # 3. Trigger Database Deletion
            # Deleting from 'auth' triggers the ON DELETE CASCADE for 'users' and related tables
            cursor.execute("DELETE FROM auth WHERE member_id = %s", (user_data['member_id'],))
            
            # commit is automatic via @with_db upon exiting this block successfully
            flash(f"Successfully deleted user and all associated records.", "success")

    except Exception as e:
        # rollback is automatic via @with_db
        print(f"Delete User Error: {e}")
        flash("An error occurred during the deletion process.", "danger")

    return redirect(url_for('admin.manage_individuals'))
@admin_bp.route('/companies')
@admin_required
@with_db
def manage_companies(conn): # conn is injected by @with_db
    companies = []
    try:
        with conn.cursor() as cursor:
            # Join auth for timestamps and jobs for the count
            sql = """
                SELECT 
                    c.comp_id, 
                    c.member_id, 
                    c.company_name, 
                    c.email, 
                    c.employee_range,
                    a.created_at,
                    COUNT(j.job_id) AS job_count
                FROM companies c
                JOIN auth a ON c.member_id = a.member_id
                LEFT JOIN jobs j ON c.comp_id = j.comp_id
                GROUP BY c.comp_id, c.member_id, c.company_name, c.email, c.employee_range, a.created_at
                ORDER BY a.created_at DESC
            """
            cursor.execute(sql)
            companies = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching companies: {e}")
        flash("Could not retrieve the company list.", "danger")

    return render_template('admin/companies.html', companies=companies)


@admin_bp.route('/delete-company/<int:comp_id>', methods=['POST']) # Secured with POST
@admin_required
@with_db
def delete_company(conn, comp_id): # conn is injected by @with_db
    try:
        with conn.cursor() as cursor:
            # 1. Fetch identifiers BEFORE deleting from the database
            sql_fetch = "SELECT member_id, logo_public_id FROM companies WHERE comp_id = %s"
            cursor.execute(sql_fetch, (comp_id,))
            company_data = cursor.fetchone()

            if not company_data:
                flash("Company not found.", "danger")
                return redirect(url_for('admin.manage_companies'))

            # 2. Cleanup Cloudinary assets
            public_id = company_data.get('logo_public_id')
            if public_id:
                import cloudinary.uploader
                try:
                    # Remove the logo from the internet
                    cloudinary.uploader.destroy(public_id)
                except Exception as c_error:
                    # Log error but don't interrupt the DB process
                    print(f"Cloudinary cleanup failed for {public_id}: {c_error}")

            # 3. Trigger Database Cascade
            # Wiping 'auth' deletes linked records in 'companies' and 'jobs'
            cursor.execute("DELETE FROM auth WHERE member_id = %s", (company_data['member_id'],))
            
            # commit is automatic via @with_db on success
            flash(f"Company {company_data['member_id']} and all linked job posts deleted successfully.", "success")

    except Exception as e:
        # rollback is automatic via @with_db on failure
        print(f"Delete Company Error: {e}")
        flash("An internal error occurred during deletion.", "danger")

    return redirect(url_for('admin.manage_companies'))

@admin_bp.route('/manage-news', methods=['GET', 'POST'])
@admin_required
@with_db
def manage_news(conn): # conn injected by @with_db
    all_news = []
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')

        try:
            with conn.cursor() as cursor:
                # 1. Insert the news article
                sql = "INSERT INTO news_posts (title, content, category) VALUES (%s, %s, %s)"
                cursor.execute(sql, (title, content, category))

                # --- BROADCAST LOGIC ---
                notif_data = []

                # A. Fetch Individuals (user_id)
                cursor.execute("SELECT user_id FROM users")
                for row in cursor.fetchall():
                    notif_data.append((row['user_id'], 'news', f"Flash News: {title}", 'individual'))

                # B. Fetch Companies (comp_id)
                cursor.execute("SELECT comp_id FROM companies")
                for row in cursor.fetchall():
                    notif_data.append((row['comp_id'], 'news', f"Flash News: {title}", 'company'))

                # 2. Bulk Insert Notifications
                if notif_data:
                    cursor.executemany("""
                        INSERT INTO notifications (user_id, type, message, user_role) 
                        VALUES (%s, %s, %s, %s)
                    """, notif_data)

                # conn.commit() is automatic here via decorator
                flash("News published & Community notified!", "success")
                return redirect(url_for('admin.manage_news')) 
                
        except Exception as e:
            # conn.rollback() is automatic here via decorator
            print(f"News Posting Error: {e}")
            flash("Failed to publish news. Internal error logged.", "danger")

    # GET logic: Fetch news for display
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM news_posts ORDER BY created_at DESC")
            all_news = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching news: {e}")

    return render_template('admin/manage_news.html', all_news=all_news)


@admin_bp.route('/delete-news/<int:news_id>', methods=['POST'])
@admin_required
@with_db
def delete_news(conn, news_id): # conn injected by @with_db
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM news_posts WHERE news_id = %s", (news_id,))
        
        flash("Article deleted successfully.", "warning")
    except Exception as e:
        print(f"Error deleting article: {e}")
        flash("Could not delete the article.", "danger")
    
    return redirect(url_for('admin.manage_news'))
@admin_bp.route('/manage-quiz', methods=['GET', 'POST'])
@admin_required
@with_db
def manage_quiz(conn): # conn injected by @with_db
    if request.method == 'POST':
        question = request.form.get('question')
        a = request.form.get('option_a')
        b = request.form.get('option_b')
        c = request.form.get('option_c')
        d = request.form.get('option_d')
        correct = request.form.get('correct_option')

        try:
            with conn.cursor() as cursor:
                # 1. Atomic Update: Wipe and Replace
                cursor.execute("DELETE FROM daily_quiz")
                sql = """INSERT INTO daily_quiz (id, question, option_a, option_b, option_c, option_d, correct_option) 
                         VALUES (1, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (question, a, b, c, d, correct))

                # --- BROADCAST LOGIC ---
                quiz_notifs = []

                # A. Individuals
                cursor.execute("SELECT user_id FROM users")
                for row in cursor.fetchall():
                    quiz_notifs.append((row['user_id'], 'quiz', "Brain Teaser: A new Daily Quiz is live!", 'individual'))

                # B. Companies
                cursor.execute("SELECT comp_id FROM companies")
                for row in cursor.fetchall():
                    quiz_notifs.append((row['comp_id'], 'quiz', "Brain Teaser: A new Daily Quiz is live!", 'company'))

                # 2. Bulk Insert Notifications
                if quiz_notifs:
                    cursor.executemany("""
                        INSERT INTO notifications (user_id, type, message, user_role) 
                        VALUES (%s, %s, %s, %s)
                    """, quiz_notifs)
                
                # Transaction committed automatically by decorator
                flash("Daily Quiz Updated & Everyone Notified!", "success")
                
        except Exception as e:
            # Automatic rollback occurs here if anything failed
            print(f"Quiz Update Error: {e}")
            flash("Failed to update quiz. Transaction rolled back.", "danger")
            
        return redirect(url_for('admin.manage_quiz'))

    # GET logic
    current_quiz = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM daily_quiz WHERE id = 1")
            current_quiz = cursor.fetchone()
    except Exception as e:
        print(f"Error fetching quiz: {e}")
    
    return render_template('admin/manage_quiz.html', quiz=current_quiz)

@admin_bp.route('/logout')
def logout():
    # Completely wipe the session for security
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('admin.login'))