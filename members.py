from flask import Blueprint, render_template, session, redirect, url_for
from chat import get_sender_details, with_db

members_bp = Blueprint('members', __name__)
@members_bp.route('/dashboard/find-members')
@with_db
def find_members(conn):
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return redirect(url_for('auth.login'))

    matched_members = []

    try:
        with conn.cursor() as cursor:
            # --- CASE 1: LOGGED IN AS INDIVIDUAL ---
            if role == 'individual':
                cursor.execute("SELECT user_id, pro_id FROM users WHERE member_id = %s", (user_id,))
                current_user = cursor.fetchone()

                if current_user:
                    actual_id = current_user['user_id']
                    my_pro_id = current_user['pro_id']

                    cursor.execute("SELECT skill_id FROM user_skills WHERE user_id = %s", (actual_id,))
                    skill_ids = [row['skill_id'] for row in cursor.fetchall()]

                    query = """
                        SELECT DISTINCT u.member_id, u.first_name, u.second_name, u.pic_path, 
                                        u.experience, p.pro_name
                        FROM users u
                        JOIN profession p ON u.pro_id = p.pro_id
                        LEFT JOIN user_skills us ON u.user_id = us.user_id
                        WHERE (u.pro_id = %s 
                    """
                    params = [my_pro_id]
                    if skill_ids:
                        query += " OR us.skill_id IN %s"
                        params.append(tuple(skill_ids))
                    
                    query += ") AND u.member_id != %s"
                    params.append(user_id)
                    cursor.execute(query, tuple(params))
                    matched_members = cursor.fetchall()

            # --- CASE 2: LOGGED IN AS COMPANY ---
            elif role == 'company':
                cursor.execute("SELECT comp_id FROM companies WHERE member_id = %s", (user_id,))
                company_data = cursor.fetchone()
                
                if company_data:
                    comp_id = company_data['comp_id']
                    cursor.execute("SELECT pro_id FROM comp_services WHERE comp_id = %s", (comp_id,))
                    service_ids = [row['pro_id'] for row in cursor.fetchall()]

                    if service_ids:
                        query = """
                            SELECT u.member_id, u.first_name, u.second_name, u.pic_path, 
                                   u.experience, p.pro_name
                            FROM users u
                            JOIN profession p ON u.pro_id = p.pro_id
                            WHERE u.pro_id IN %s
                        """
                        cursor.execute(query, (tuple(service_ids),))
                        matched_members = cursor.fetchall()

        # --- DATA POST-PROCESSING (Connection is closed/returned by here) ---
        for member in matched_members:
            pic_val = member.get('pic_path')
            if pic_val and (pic_val.startswith('http://') or pic_val.startswith('https://')):
                member['avatar'] = pic_val
            else:
                first_name = member.get('first_name', 'User')
                member['avatar'] = f"https://ui-avatars.com/api/?name={first_name}&background=0d6efd&color=fff"

        # Fetch layout details
        display_name, profile_url, _, _ = get_sender_details(user_id, role)
        
        return render_template('dashboard/find_matches.html', 
                                members=matched_members,
                                name=display_name,        
                                profile_url=profile_url,  
                                active_page='members',
                                hide_overview=True)

    except Exception as e:
        print(f"Matching Error: {e}")
        return f"An error occurred: {e}", 500