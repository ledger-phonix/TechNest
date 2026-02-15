import pymysql
from datetime import datetime
import os
from functools import wraps
from dbutils.pooled_db import PooledDB


from dotenv import load_dotenv
load_dotenv()
# --- 1. Central Connection Helper ---
# 1. Initialize the Pool ONCE (This lives as long as your Flask app runs)
db_pool = PooledDB(
    creator=pymysql,
    maxconnections=10,    # Max parallel connections
    mincached=2,         # Keep at least 2 connections "warm" at all times
    blocking=True,
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT')),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    ssl={'ssl_mode': 'REQUIRED'},
    init_command="SET time_zone = '+05:00'"
)
def with_db(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        conn = db_pool.connection() # Instant grab from pool
        try:
            # Inject 'conn' as the first argument
            result = f(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            print(f"Database Error in {f.__name__}: {e}")
            raise e
        finally:
            conn.close() # Sends back to pool
    return decorated_function
def get_db_connection():
    """Grabs an INSTANT connection from the warm pool."""
    return db_pool.connection()



# --- 2. Existing Search Function (Kept as is) ---
@with_db
def search_suggestions(conn, table_name, id_col, name_col, query):
    # 1. SECURITY: Whitelist both Tables AND Columns
    allowed_tables = ['profession', 'skills_list']
    allowed_cols = ['pro_id', 'pro_name', 'skill_id', 'skill_name']

    if table_name not in allowed_tables or id_col not in allowed_cols or name_col not in allowed_cols:
        print(f"Blocked suspicious search attempt on: {table_name}")
        return []

    try:
        with conn.cursor() as cursor:
            # Table/Col names can't be %s, but we've whitelisted them above for safety
            sql = f"SELECT {id_col} AS id, {name_col} AS name FROM {table_name} WHERE {name_col} LIKE %s LIMIT 5"
            cursor.execute(sql, (f"%{query}%",))
            return cursor.fetchall()
    except Exception as e:
        print(f"Search Error: {e}")
        return []

@with_db
def is_email_registered(conn, email):
    """Checks if an email already exists in the auth table."""
    try:
        with conn.cursor() as cursor:
            sql = "SELECT email FROM auth WHERE email = %s"
            cursor.execute(sql, (email,))
            result = cursor.fetchone()
            return result is not None 
    except Exception as e:
        print(f"Error checking email: {e}")
        return True # Safety: Don't allow registration if query fails
@with_db
def save_individual_transaction(conn, auth_data, user_data, skill_ids_list):
    """
    Saves Auth, User Profile, and Skills in ONE transaction.
    Decorator handles commit/rollback automatically.
    """
    try:
        with conn.cursor() as cursor:
            # A. Insert into AUTH table
            sql_auth = """
                INSERT INTO auth (member_id, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_auth, (
                auth_data['member_id'], 
                auth_data['email'], 
                auth_data['password_hash'], 
                'individual'
            ))

            # B. Insert into USERS table
            sql_user = """
                INSERT INTO users (
                    member_id, first_name, second_name, gender, email, phone_no, 
                    city, DOB, education, experience, pro_id, tagline, pic_path, profile_public_id,
                    linkedin_link, other_link
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql_user, (
                auth_data['member_id'],
                user_data['first_name'],
                user_data['second_name'],
                user_data['gender'],
                auth_data['email'],
                user_data['phone_no'],
                user_data['city'],
                user_data['dob'],
                user_data['education'],
                user_data['experience'],
                user_data['pro_id'],
                user_data['tagline'],
                user_data['pic_path'],
                user_data['public_id'],
                user_data['linkedin'],
                user_data['other_link']
            ))

            # C. Get the generated user_id (Auto-increment PK from 'users' table)
            user_id = cursor.lastrowid

            # D. Insert Skills (Loop)
            if skill_ids_list:
                sql_skills = "INSERT INTO user_skills (user_id, skill_id) VALUES (%s, %s)"
                for skill_id in skill_ids_list:
                    # Ensuring skill_id is an integer for the foreign key
                    cursor.execute(sql_skills, (user_id, int(skill_id)))

        # NOTE: No conn.commit() needed; the decorator does it after this return
        return True

    except Exception as e:
        # NOTE: No conn.rollback() needed; the decorator handles it on Exception
        print(f"!!! TRANSACTION FAILED (Individual): {e}")
        return False
@with_db
def save_company_transaction(conn, auth_data, comp_data, service_ids_list):
    """
    Saves Auth, Company Profile, and Services in ONE transaction.
    The decorator handles the connection start, commit, and rollback.
    """
    try:
        with conn.cursor() as cursor:
            # A. Insert into AUTH table
            sql_auth = """
                INSERT INTO auth (member_id, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_auth, (
                auth_data['member_id'], 
                auth_data['email'], 
                auth_data['password_hash'], 
                'company'
            ))

            # B. Insert into COMPANIES table
            sql_comp = """
                INSERT INTO companies (
                    member_id, company_name, owner_name, established_year, 
                    employee_range, city, address, google_map_url, about, 
                    company_logo, logo_public_id, email, web_url, linkedin_url, contact_no
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql_comp, (
                auth_data['member_id'],
                comp_data['company_name'],
                comp_data['owner_name'],
                comp_data['est_year'],
                comp_data['emp_range'],
                comp_data['city'],
                comp_data['address'],
                comp_data['map_url'],
                comp_data['about'],
                comp_data['logo_path'],
                comp_data['public_id'],
                auth_data['email'],
                comp_data['web_url'],
                comp_data['linkedin'],
                comp_data['contact_no']
            ))

            # C. Get the generated comp_id (Auto-increment PK from companies table)
            comp_id = cursor.lastrowid

            # D. Insert Services (Loop)
            if service_ids_list:
                sql_services = "INSERT INTO comp_services (comp_id, pro_id) VALUES (%s, %s)"
                for pro_id in service_ids_list:
                    # Ensuring pro_id is cast to int for database compatibility
                    cursor.execute(sql_services, (comp_id, int(pro_id)))

        # Return True if we reach here; decorator handles the commit
        return True

    except Exception as e:
        # Log the specific error; decorator handles the rollback
        print(f"!!! TRANSACTION FAILED (Company): {e}")
        return False

@with_db
def get_user_for_login(conn, email):
    """Fetches credentials for authentication."""
    try:
        with conn.cursor() as cursor:
            # member_id for session, password_hash for verification, role for redirection
            sql = "SELECT member_id, password_hash, role FROM auth WHERE email = %s"
            cursor.execute(sql, (email,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Login Query Error: {e}")
        return None

@with_db
def save_reset_token(conn, email, token, expiry):
    """Saves the token and expiry time to the database."""
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE auth SET reset_token = %s, reset_expires = %s WHERE email = %s"
            cursor.execute(sql, (token, expiry, email))
            # conn.commit() is handled by decorator
    except Exception as e:
        print(f"Error saving reset token: {e}")

@with_db
def verify_reset_token(conn, token):
    """Checks if token exists and hasn't expired."""
    try:
        with conn.cursor() as cursor:
            # Comparison with datetime.now() ensures token is still valid
            sql = "SELECT email FROM auth WHERE reset_token = %s AND reset_expires > %s"
            cursor.execute(sql, (token, datetime.now()))
            return cursor.fetchone() # Returns {'email': '...'} or None
    except Exception as e:
        print(f"Error verifying token: {e}")
        return None

@with_db
def update_password_and_clear_token(conn, email, hashed_password):
    """Updates the password and deletes the token so it can't be reused."""
    try:
        with conn.cursor() as cursor:
            # We nullify the token and expiry to prevent reuse of the link
            sql = """
                UPDATE auth 
                SET password_hash = %s, reset_token = NULL, reset_expires = NULL 
                WHERE email = %s
            """
            cursor.execute(sql, (hashed_password, email))
            # conn.commit() is handled by the decorator upon successful return
    except Exception as e:
        print(f"Error updating password: {e}")

@with_db
def get_all_members(conn, limit=20, offset=0):
    """Fetches all members with their skills and formatted display data."""
    try:
        # Note: DictCursor is already set in your db_pool, so we just use with conn.cursor()
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    u.*, 
                    p.pro_name AS profession_name,
                    GROUP_CONCAT(s.skill_name) AS skills_combined
                FROM users u
                LEFT JOIN profession p ON u.pro_id = p.pro_id
                LEFT JOIN user_skills us ON u.user_id = us.user_id
                LEFT JOIN skills_list s ON us.skill_id = s.skill_id
                GROUP BY u.user_id
                ORDER BY u.first_name ASC, u.second_name ASC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, (limit, offset))
            members = cursor.fetchall()

            for member in members:
                # 1. Process Skills
                combined = member.get('skills_combined')
                member['skills'] = combined.split(',') if combined else []
                
                # 2. Format Display Name
                f_name = member.get('first_name') or ''
                s_name = member.get('second_name') or ''
                member['display_name'] = f"{f_name} {s_name}".strip()
                
                # 3. Handle Profile Image
                db_photo = member.get('pic_path') 
                if db_photo and (db_photo.startswith('http://') or db_photo.startswith('https://')):
                    member['profile_image'] = db_photo
                else:
                    # Fallback to UI-Avatar
                    member['profile_image'] = f"https://ui-avatars.com/api/?name={member['display_name']}&background=random"
            
            return members
    except Exception as e:
        print(f"Database Error in get_all_members: {e}")
        return []

@with_db
def get_members_count(conn):
    """Returns the total number of registered users."""
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM users")
            result = cursor.fetchone()
            return result['total'] if result else 0
    except Exception as e:
        print(f"Error in get_members_count: {e}")
        return 0
@with_db
def get_all_companies(conn, limit=20, offset=0):
    """Fetches all companies with services and handles logo fallback logic."""
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    c.*, 
                    GROUP_CONCAT(p.pro_name SEPARATOR ', ') as services_combined
                FROM companies c
                LEFT JOIN comp_services cs ON c.comp_id = cs.comp_id
                LEFT JOIN profession p ON cs.pro_id = p.pro_id
                GROUP BY c.comp_id
                ORDER BY c.company_name ASC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, (limit, offset))
            companies = cursor.fetchall()

            for comp in companies:
                # 1. Process services string into list
                combined = comp.get('services_combined')
                comp['services'] = combined.split(', ') if combined else []
                
                # 2. Logo path logic
                db_logo = comp.get('company_logo')

                # Check for Cloudinary/Full URL
                if not (db_logo and (db_logo.startswith('http://') or db_logo.startswith('https://'))):
                    # Fallback to UI-Avatar if logo is missing or local
                    name_for_url = comp['company_name'].replace(' ', '+')
                    comp['company_logo'] = f"https://ui-avatars.com/api/?name={name_for_url}&background=0D8ABC&color=fff"
            
            return companies
    except Exception as e:
        print(f"Database Error in get_all_companies: {e}")
        return []

@with_db
def get_companies_count(conn):
    """Returns total count of companies."""
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM companies")
            result = cursor.fetchone()
            return result['total'] if result else 0
    except Exception as e:
        print(f"Count Error: {e}")
        return 0
        

@with_db
def get_public_jobs(conn, limit=20, offset=0):
    """Fetches all active jobs with company info and skills."""
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT j.*, j.job_type, c.company_name, c.company_logo, c.city,
                       GROUP_CONCAT(s.skill_name SEPARATOR ', ') as skills
                FROM jobs j
                JOIN companies c ON j.comp_id = c.comp_id
                LEFT JOIN job_skills js ON j.job_id = js.job_id
                LEFT JOIN skills_list s ON js.skill_id = s.skill_id
                WHERE j.expires_at > NOW()
                GROUP BY j.job_id 
                ORDER BY j.created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, (limit, offset))
            jobs = cursor.fetchall()

            # Apply Logo Logic
            for job in jobs:
                db_logo = job.get('company_logo')
                
                # Check for Cloudinary/HTTP link
                if not (db_logo and (db_logo.startswith('http://') or db_logo.startswith('https://'))):
                    # Fallback to UI-Avatar using the company name
                    name_for_url = job.get('company_name', 'Company').replace(' ', '+')
                    job['company_logo'] = f"https://ui-avatars.com/api/?name={name_for_url}&background=0D8ABC&color=fff"

            return jobs
    except Exception as e:
        print(f"DB Error (get_public_jobs): {e}")
        return []

@with_db
def get_jobs_count(conn):
    """Returns the total number of active jobs."""
    try:
        with conn.cursor() as cursor:
            # Note: We use COUNT(*) as total to keep dict access consistent
            cursor.execute("SELECT COUNT(*) as total FROM jobs WHERE expires_at > NOW()")
            result = cursor.fetchone()
            return result['total'] if result else 0
    except Exception as e:
        print(f"DB Error (get_jobs_count): {e}")
        return 0
    
@with_db
def get_user_dashboard_data(conn, member_id, role):
    """Fetches role-specific profile data for the dashboard with universal image handling."""
    try:
        with conn.cursor() as cursor:
            if role == 'company':
                # Fetching 'company_logo' as 'pic_path' to keep logic uniform
                sql = """
                    SELECT company_name AS name, company_logo AS pic_path, 
                           email, about, city 
                    FROM companies WHERE member_id = %s
                """
            else:
                sql = """
                    SELECT first_name, second_name, pic_path, 
                           email, tagline AS about, city 
                    FROM users WHERE member_id = %s
                """
            
            cursor.execute(sql, (member_id,))
            user = cursor.fetchone()

            if user:
                # 1. Handle Name (Individual needs first + second concatenated)
                if role == 'individual':
                    first = user.get('first_name') or ''
                    second = user.get('second_name') or ''
                    user['name'] = f"{first} {second}".strip()
                
                # 2. Universal Image Handling
                pic = user.get('pic_path')
                
                # Check if it's already a full Cloudinary/Web URL
                if pic and (pic.startswith('http://') or pic.startswith('https://')):
                    user['profile_url'] = pic
                else:
                    # Fallback Logic: Clean name for URL safety
                    clean_name = user['name'].replace(' ', '+')
                    
                    if role == 'company':
                        # Company fallback (Corporate Blue)
                        user['profile_url'] = f"https://ui-avatars.com/api/?name={clean_name}&background=0D8ABC&color=fff"
                    else:
                        # Individual fallback (Standard Bootstrap Blue)
                        user['profile_url'] = f"https://ui-avatars.com/api/?name={clean_name}&background=0d6efd&color=fff"
                
                return user
            
            return None

    except Exception as e:
        print(f"Error fetching dashboard data for {member_id}: {e}")
        return None
        
@with_db
def get_detailed_profile_data(conn, member_id, role):
    """Fetches full profile details (individual or company) including joined tables."""
    try:
        with conn.cursor() as cursor:
            if role == 'individual':
                query = """
                    SELECT 
                        u.*, 
                        p.pro_name AS profession_name,
                        GROUP_CONCAT(s.skill_name) AS skills_combined,
                        GROUP_CONCAT(s.skill_id) AS skills_ids_combined
                    FROM users u
                    LEFT JOIN profession p ON u.pro_id = p.pro_id
                    LEFT JOIN user_skills us ON u.user_id = us.user_id
                    LEFT JOIN skills_list s ON us.skill_id = s.skill_id
                    WHERE u.member_id = %s
                    GROUP BY u.user_id
                """
            else:
                query = """
                    SELECT 
                        c.*,
                        GROUP_CONCAT(p.pro_name) AS services_names_combined,
                        GROUP_CONCAT(p.pro_id) AS services_ids_combined
                    FROM companies c
                    LEFT JOIN comp_services cs ON c.comp_id = cs.comp_id
                    LEFT JOIN profession p ON cs.pro_id = p.pro_id
                    WHERE c.member_id = %s
                    GROUP BY c.comp_id
                """
            
            cursor.execute(query, (member_id,))
            member = cursor.fetchone()

            if member:
                # 1. Image Logic (Cloudinary-Aware)
                pic_col = 'pic_path' if role == 'individual' else 'company_logo'
                val = member.get(pic_col)

                if val and (val.startswith('http://') or val.startswith('https://')):
                    member['profile_url'] = val
                else:
                    # Fallback to UI-Avatars
                    if role == 'individual':
                        name = f"{member.get('first_name', '')} {member.get('second_name', '')}".strip()
                        bg_color = "0d6efd"
                    else:
                        name = member.get('company_name', 'Company')
                        bg_color = "0D8ABC"
                    
                    name_param = name.replace(' ', '+') if name else 'User'
                    member['profile_url'] = f"https://ui-avatars.com/api/?name={name_param}&background={bg_color}&color=fff"

                # 2. Data Formatting for Chips/Lists
                if role == 'individual':
                    # Split comma-separated skills into a simple list
                    member['skills'] = member['skills_combined'].split(',') if member.get('skills_combined') else []
                else:
                    # Transform services into a list of dictionaries for the frontend loop
                    services_list = []
                    names = member.get('services_names_combined').split(',') if member.get('services_names_combined') else []
                    ids = member.get('services_ids_combined').split(',') if member.get('services_ids_combined') else []
                    
                    # Ensure we don't crash if counts don't match for some reason
                    for i in range(len(names)):
                        services_list.append({
                            'pro_id': ids[i], 
                            'pro_name': names[i]
                        })
                    
                    member['services'] = services_list
                    # Stored as a string for the hidden input field in the edit form
                    member['services_ids_list'] = member.get('services_ids_combined', '')

                return member
            return None

    except Exception as e:
        print(f"Database Error in get_detailed_profile_data: {e}")
        return None