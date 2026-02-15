
from datetime import datetime, timedelta
from flask import Blueprint, request, session, current_app, url_for, render_template, redirect, jsonify, make_response
from flask_socketio import emit
from werkzeug.utils import secure_filename
from db_manager import get_db_connection
from auth import save_to_cloudinary
# import pymysql # Add this
import cloudinary.uploader
from pymysql.cursors import DictCursor # And this
from db_manager import with_db
# 1. Create a Blueprint for HTTP routes (like file uploads)
chat_bp = Blueprint('chat', __name__)

@with_db
def get_sender_details(conn, member_id, role):
    """
    Carefully rewritten to use the connection pool via decorator.
    Returns: name, display_pic, member_id, db_pic_val
    """
    # 1. Use the 'conn' injected by the decorator
    with conn.cursor() as cursor:
        # Defaults
        name = "User" if role == 'individual' else "Company"
        db_pic_val = None 
        
        try:
            if role == 'individual':
                cursor.execute("SELECT first_name, pic_path FROM users WHERE member_id = %s", (member_id,))
                res = cursor.fetchone()
                if res:
                    name = res.get('first_name') or "User"
                    db_pic_val = res.get('pic_path')
            else:
                cursor.execute("SELECT company_name, company_logo FROM companies WHERE member_id = %s", (member_id,))
                res = cursor.fetchone()
                if res:
                    name = res.get('company_name') or "Company"
                    db_pic_val = res.get('company_logo')
            
            # 2. Handle Image Logic (Cloudinary vs UI-Avatars)
            if db_pic_val and str(db_pic_val).startswith('http'):
                # It's a Cloudinary URL, use it directly
                display_pic = db_pic_val
            else:
                # Fallback to UI-Avatars
                # Clean name for URL (removes spaces/special characters)
                clean_name = name.replace(" ", "+")
                bg_color = "0d6efd" if role == 'individual' else "0D8ABC"
                display_pic = f"https://ui-avatars.com/api/?name={clean_name}&background={bg_color}&color=fff"
            
            return name, display_pic, member_id, db_pic_val
            
        except Exception as e:
            print(f"Error in get_sender_details: {e}")
            # Safe fallbacks if query fails
            return name, f"https://ui-avatars.com/api/?name={role}", member_id, None
# 3. SocketIO Event Registration
# We wrap these in a function so app.py can pass the 'socketio' instance here
def init_chat_socket(socketio):
    
    @socketio.on('send_community_msg')
    @with_db
    def handle_message(conn, data): # conn is injected here by the decorator
        member_id = session.get('user_id')
        role = session.get('role')
        
        # Get text message AND file data from the 'data' dictionary
        message_text = data.get('message', '').strip()
        file_path = data.get('file_path', None) 
        file_name = data.get('file_name', None) 
        file_public_id = data.get('file_public_id', None)

        # Get user details for the broadcast
        # Note: get_sender_details is also decorated, so it manages its own connection
        display_name, avatar, sender_m_id, _ = get_sender_details(member_id, role)

        # Save to Database
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO community_chat 
                        (sender_id, sender_role, message, file_path, file_name, file_public_id) 
                        VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (member_id, role, message_text, file_path, file_name, file_public_id))
                # conn.commit() is handled automatically by @with_db on success
        except Exception as e:
            print(f"Database Save Error in Socket: {e}")
            # The decorator will handle the rollback automatically

        # BROADCAST: This sends the data back to the JavaScript
        emit('receive_community_msg', {
            'name': display_name,
            'avatar': avatar,
            'role': role,
            'message': message_text,
            'sender_member_id': sender_m_id,
            'file_path': file_path,
            'file_name': file_name,
            'time': datetime.now().strftime('%I:%M %p')
        }, broadcast=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'zip', 'txt', 'rar'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
@with_db
def get_chat_history(conn):
    with conn.cursor() as cursor:
        # 1. ONE QUERY to get messages AND sender details at once (The Speed Secret)
        sql = """
            SELECT 
                m.*,
                u.first_name AS u_name, u.pic_path AS u_pic, u.member_id AS u_mid,
                c.company_name AS c_name, c.company_logo AS c_pic, c.member_id AS c_mid
            FROM community_chat m
            LEFT JOIN users u ON m.sender_id = u.member_id AND m.sender_role = 'individual'
            LEFT JOIN companies c ON m.sender_id = c.member_id AND m.sender_role = 'company'
            ORDER BY m.created_at DESC LIMIT 50
        """
        cursor.execute(sql)
        messages = list(cursor.fetchall()) 
        messages.reverse()
        
        for msg in messages:
            # 2. Logic to determine display values (No DB calls here = Fast!)
            if msg['sender_role'] == 'individual':
                name = msg.get('u_name') or "User"
                raw_file = msg.get('u_pic')
                m_id = msg.get('u_mid')
                bg_color = "0d6efd"
            else:
                name = msg.get('c_name') or "Company"
                raw_file = msg.get('c_pic')
                m_id = msg.get('c_mid')
                bg_color = "0D8ABC"

            # 3. Process Avatar URL
            if raw_file and str(raw_file).startswith('http'):
                full_pic_url = raw_file
            else:
                full_pic_url = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background={bg_color}&color=fff"
            # Inside your for msg in messages loop:

            f_path = msg.get('file_path')
            if f_path:
                f_path = str(f_path) # Force to string
                if f_path.startswith('http'):
                    # 1. If it's a Cloudinary link, use it
                    msg['file_path'] = f_path
                elif f_path.strip() == "" or f_path == "None":
                    # 2. If it's empty, null it out so the HTML doesn't try to load it
                    msg['file_path'] = None
                else:
                    None
            # 4. Fill the msg object with your exact required keys
            msg['display_name'] = name
            msg['avatar'] = full_pic_url
            msg['raw_file'] = raw_file
            msg['sender_member_id'] = m_id # <--- This fixes your profile link!
            msg['is_comp'] = (msg['sender_role'] == 'company')
            msg['formatted_time'] = msg['created_at'].strftime('%I:%M %p')

            # 5. Fix Chat File Paths (Cloudinary check)
           
        
        return messages
        
@chat_bp.route('/dashboard/community-chat')
def community_chat_page():
    user_id = session.get('user_id')
    role = session.get('role') 
    
    if not user_id:
        return redirect(url_for('auth.login'))
    
    # 1. FETCH DATA (Decorators handle connections automatically)
    # Note: We do NOT pass 'conn' here anymore.
    display_name, profile_url, _, _ = get_sender_details(user_id, role)
    history = get_chat_history() 
    
    # 2. FORMATTING
    display_role = role.capitalize() if role else "User"
    
    # 3. RENDER RESPONSE
    response = make_response(render_template(
        'dashboard/chat.html',
        chat_history=history, 
        user_role=display_role,
        name=display_name,
        profile_url=profile_url
    ))
    
    # 4. FORCE RELOAD HEADERS (Security & History Fix)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

# --- REPLACE ALL '/chat/upload' ROUTES WITH THIS ONE ---

@chat_bp.route('/chat/upload', methods=['POST'])
def handle_chat_upload():
    # 1. Basic Validation
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    # 2. SECURITY CHECK (Crucial!)
    # Ensure you have the allowed_file function imported or defined
    if not allowed_file(file.filename):
        return jsonify({
            'success': False, 
            'error': 'File type not allowed! Use PDF, ZIP, or Images.'
        }), 400

    member_id = session.get('user_id')
    
    try:
        # 3. Call Cloudinary Wrapper
        # We pass member_id because your save function needs it for logic
        file_url, public_id = save_to_cloudinary(file, 'chat', member_id)
        
        if file_url and public_id:
            # 4. Return Success
            return jsonify({
                'success': True,
                'file_path': file_url,      # The secure HTTPS link
                'file_name': file.filename, # Original name for display
                'file_public_id': public_id # Saved for deletion logic
            })
        else:
            return jsonify({'success': False, 'error': 'Cloudinary upload returned None'}), 500

    except Exception as e:
        print(f"UPLOAD ERROR: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
        
@with_db
def cleanup_old_chats(conn, app): # conn is injected by @with_db
    """Deletes chat records and physical files older than 24 hours."""
    # We still need app_context if this is called from an external script
    with app.app_context():
        # 1. Calculate time threshold
        limit = datetime.now() - timedelta(hours=24)
        
        try:
            with conn.cursor() as cursor:
                # 2. Fetch public_ids BEFORE deleting rows
                # Security: Filtering for NOT NULL ensures we don't call Cloudinary for text-only msgs
                cursor.execute("""
                    SELECT file_public_id 
                    FROM community_chat 
                    WHERE created_at < %s AND file_public_id IS NOT NULL
                """, (limit,))
                old_files = cursor.fetchall()

                print(f"Found {len(old_files)} files to delete from Cloud.")

                # 3. Loop through and delete from Cloudinary
                for f in old_files:
                    public_id = f.get('file_public_id')
                    if not public_id:
                        continue
                        
                    try:
                        # Attempt 1: Image type
                        result = cloudinary.uploader.destroy(public_id, resource_type="image")
                        
                        # Attempt 2: Raw type (PDFs, ZIPs, etc.)
                        if result.get('result') != 'ok':
                            cloudinary.uploader.destroy(public_id, resource_type="raw")
                            
                        print(f"Deleted Cloudinary Asset: {public_id}")
                    except Exception as c_error:
                        print(f"Cloudinary Delete Error for {public_id}: {c_error}")

                # 4. Delete database records
                # This is atomic: if this fails, the decorator won't commit
                cursor.execute("DELETE FROM community_chat WHERE created_at < %s", (limit,))
                
                # Manual conn.commit() is no longer needed; handled by @with_db
                print(f"Cleanup finished. Database cleared for records older than {limit}")
                
        except Exception as e:
            print(f"Cleanup failed during DB operation: {e}")
            # Decorator handles rollback automatically
            raise e