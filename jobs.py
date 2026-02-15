from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from datetime import datetime, timedelta
from pymysql.cursors import DictCursor
# Learning from your provided code: use get_sender_details for header info
from chat import get_db_connection, get_sender_details
from dashboard import login_required 

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/dashboard/jobs', methods=['GET', 'POST'])
@login_required
def manage_jobs():
    user_id = session.get('user_id')
    role = session.get('role')

    # Security: Only companies should access this management center
    if role != 'company':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('dashboard.index'))

    conn = get_db_connection()
    cursor = conn.cursor(DictCursor)

    try:
        # 1. FETCH HEADER INFO (Learning from your code pattern)
        # This fixes the picture and name appearing issue in the top right
        display_name, profile_url, _, _ = get_sender_details(user_id, role)

        # 2. HANDLE NEW JOB POSTING (POST)
        if request.method == 'POST':
            job_role = request.form.get('job_role')
            job_type = request.form.get('job_type')
            desc = request.form.get('job_description')
            link = request.form.get('external_link')
            skills_ids = request.form.get('skills_list')
            expiry_date = datetime.now() + timedelta(days=10)
            
            # Get the internal comp_id for this user
            cursor.execute("SELECT comp_id FROM companies WHERE member_id = %s", (user_id,))
            comp_data = cursor.fetchone()
            
            if comp_data:
                comp_id = comp_data['comp_id']

                # Insert Job Listing
                cursor.execute("""
                    INSERT INTO jobs (comp_id, job_role, job_description, job_type, external_link, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (comp_id, job_role, desc, job_type, link, expiry_date))
                
                job_id = cursor.lastrowid

                # Insert Skill Tags
                if skills_ids:
                    id_list = [int(s_id.strip()) for s_id in skills_ids.split(',') if s_id.strip()]
                    for s_id in id_list:
                        cursor.execute("INSERT INTO job_skills (job_id, skill_id) VALUES (%s, %s)", (job_id, s_id))
                    # --- NEW NOTIFICATION LOGIC START ---
                    # 1. Find all users who have at least one of these skill IDs
                    # We use a tuple for the IN clause
                    cursor.execute("""
                        SELECT DISTINCT u.user_id 
                        FROM user_skills us
                        JOIN users u ON us.user_id = u.user_id
                        WHERE us.skill_id IN %s
                    """, (tuple(id_list),))
                    
                    matching_users = cursor.fetchall()

                    # 2. Insert notification for each matched individual
                    for user in matching_users:
                        notif_msg = f"New Job Alert: A position for '{job_role}' matches your skills!"
                        cursor.execute("""
                            INSERT INTO notifications (user_id, type, message) 
                            VALUES (%s, 'job_match', %s)
                        """, (user['user_id'], notif_msg))
                    # --- NEW NOTIFICATION LOGIC END ---
                conn.commit()
                flash("Job opportunity launched successfully!", "success")
            
            return redirect(url_for('jobs.manage_jobs'))

        # 3. FETCH ACTIVE LISTINGS (GET)
        cursor.execute("""
            SELECT j.*, DATEDIFF(j.expires_at, NOW()) as days_left,
                   GROUP_CONCAT(s.skill_name SEPARATOR ', ') as required_skills
            FROM jobs j
            JOIN companies c ON j.comp_id = c.comp_id
            LEFT JOIN job_skills js ON j.job_id = js.job_id
            LEFT JOIN skills_list s ON js.skill_id = s.skill_id
            WHERE c.member_id = %s AND j.expires_at > NOW()
            GROUP BY j.job_id 
            ORDER BY j.created_at DESC
        """, (user_id,))
        
        active_jobs = cursor.fetchall()

    except Exception as e:
        print(f"Jobs Management Error: {e}")
        flash("A system error occurred. Please try again.", "danger")
        active_jobs = []
    finally:
        cursor.close()
        conn.close()

    # Rendering the unified template with header data
    return render_template('dashboard/jobs_center.html', 
                           jobs=active_jobs, 
                           name=display_name, 
                           profile_url=profile_url,
                           role=role,
                           active_page='jobs')
    
    
@jobs_bp.route('/dashboard/jobs/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(DictCursor)

    try:
        # Verify ownership: Ensure the job belongs to the logged-in company
        query = """
            SELECT j.job_id 
            FROM jobs j 
            JOIN companies c ON j.comp_id = c.comp_id 
            WHERE j.job_id = %s AND c.member_id = %s
        """
        cursor.execute(query, (job_id, user_id))
        job = cursor.fetchone()

        if job:
            # Delete from job_skills first (though ON DELETE CASCADE handles this, it's good practice)
            cursor.execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))
            conn.commit()
            flash("Listing removed successfully.", "info")
        else:
            flash("Unauthorized action or job not found.", "danger")

    except Exception as e:
        conn.rollback()
        print(f"Delete Error: {e}")
        flash("Could not delete the job.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('jobs.manage_jobs'))

@jobs_bp.route('/dashboard/job-feed')
@login_required
def job_feed():
    user_id = session.get('user_id') # This is the member_id from auth
    role = session.get('role')

    if role != 'individual':
        return redirect(url_for('jobs.manage_jobs'))

    conn = get_db_connection()
    cursor = conn.cursor(DictCursor)

    try:
        # 1. Get header info
        display_name, profile_url, _, _ = get_sender_details(user_id, role)

        # 2. FETCH MATCHED JOBS
        # We join 'users' to bridge session.member_id to user_skills.user_id
        query = """
                SELECT   j.*, 
                    c.company_name, c.company_logo, c.comp_id, c.member_id,
                    DATEDIFF(j.expires_at, NOW()) as days_left,
                    (SELECT GROUP_CONCAT(s.skill_name SEPARATOR ', ') 
                        FROM job_skills js2 
                        JOIN skills_list s ON js2.skill_id = s.skill_id 
                        WHERE js2.job_id = j.job_id) as all_skills
                FROM jobs j
                JOIN companies c ON j.comp_id = c.comp_id
                WHERE j.job_id IN (
                    -- Only include jobs that match at least one of the user's skills
                    SELECT js.job_id 
                    FROM job_skills js
                    JOIN user_skills us ON js.skill_id = us.skill_id
                    JOIN users u ON us.user_id = u.user_id
                    WHERE u.member_id = %s
                ) 
                AND j.expires_at > NOW()
                ORDER BY j.created_at DESC
            """
        cursor.execute(query, (user_id,))
        matched_jobs = cursor.fetchall()
        for job in matched_jobs:
            # 1. Process logo path
            db_logo = job.get('company_logo')
            if db_logo and (db_logo.startswith('http://') or db_logo.startswith('https://')):
                # Keep the Cloudinary URL
                pass
            else:
                # Use UI-Avatar fallback
                job['company_logo'] = f"https://ui-avatars.com/api/?name={job['company_name']}&background=0D8ABC&color=fff"
        # --- NEW: Clear 'job_match' alerts when they view the feed ---
        # First, find the actual user_id from the member_id
        cursor.execute("SELECT user_id FROM users WHERE member_id = %s", (user_id,))
        u_data = cursor.fetchone()
        if u_data:
            cursor.execute("""
                UPDATE notifications 
                SET is_read = TRUE 
                WHERE user_id = %s AND type = 'job_match'
            """, (u_data['user_id'],))
            conn.commit()
        # -------------------------------------------------------------
       
    except Exception as e:
        print(f"Job Feed Error: {e}")
        matched_jobs = []
    finally:
        cursor.close()
        conn.close()

    return render_template('dashboard/job_board.html', 
                           jobs=matched_jobs, 
                           name=display_name, 
                           profile_url=profile_url,
                           active_page='jobs')