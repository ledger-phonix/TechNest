
from flask import Blueprint, render_template, session, redirect, url_for
from pymysql.cursors import DictCursor
from chat import get_sender_details, with_db

companies_bp = Blueprint('companies', __name__)

@companies_bp.route('/dashboard/find-companies')
@with_db
def find_companies(conn): # conn is injected by @with_db
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return redirect(url_for('auth.login'))

    matched_companies = []
    display_name, profile_url = None, None

    try:
        with conn.cursor() as cursor:
            # --- CASE 1: INDIVIDUAL LOOKING FOR SERVICES ---
            if role == 'individual':
                cursor.execute("SELECT pro_id FROM users WHERE member_id = %s", (user_id,))
                user_data = cursor.fetchone()

                if user_data and user_data.get('pro_id'):
                    user_pro_id = user_data['pro_id']

                    query = """
                        SELECT c.member_id, c.company_name, c.company_logo, c.city, 
                               c.established_year, c.employee_range
                        FROM companies c
                        JOIN comp_services cs ON c.comp_id = cs.comp_id
                        WHERE cs.pro_id = %s
                    """
                    cursor.execute(query, (user_pro_id,))
                    matched_companies = cursor.fetchall()

            # --- CASE 2: COMPANY LOOKING FOR PARTNERS (B2B) ---
            elif role == 'company':
                cursor.execute("""
                    SELECT cs.pro_id, c.comp_id 
                    FROM comp_services cs 
                    JOIN companies c ON cs.comp_id = c.comp_id 
                    WHERE c.member_id = %s
                """, (user_id,))
                services_data = cursor.fetchall()
                
                if services_data:
                    service_ids = [row['pro_id'] for row in services_data]
                    my_comp_id = services_data[0]['comp_id']

                    # Securely handle the IN clause
                    query = """
                        SELECT DISTINCT c.member_id, c.company_name, c.company_logo, c.city, 
                                        c.established_year, c.employee_range
                        FROM companies c
                        JOIN comp_services cs ON c.comp_id = cs.comp_id
                        WHERE cs.pro_id IN %s AND c.comp_id != %s
                    """
                    cursor.execute(query, (tuple(service_ids), my_comp_id))
                    matched_companies = cursor.fetchall()

        # --- DATA POST-PROCESSING (Outside the cursor context) ---
        for comp in matched_companies:
            logo_val = comp.get('company_logo')
            if logo_val and (logo_val.startswith('http://') or logo_val.startswith('https://')):
                comp['logo_url'] = logo_val
            else:
                comp_name = comp.get('company_name', 'Company')
                comp['logo_url'] = f"https://ui-avatars.com/api/?name={comp_name}&background=0D8ABC&color=fff"

        # Fetch layout details
        display_name, profile_url, _, _ = get_sender_details(user_id, role)

    except Exception as e:
        print(f"Company Matching Error: {e}")
    

    return render_template('dashboard/find_companies.html', 
                            companies=matched_companies,
                            name=display_name,
                            profile_url=profile_url,
                            active_page='companies',
                            hide_overview=True)