from werkzeug.security import generate_password_hash
from db_manager import get_db_connection

def create_initial_admin():
    username = "admin_boss"
    email = "admin@technest.com"
    password = "@Phonix123" # CHANGE THIS
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO admins (username, email, password_hash) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, email, hashed_pw))
            conn.commit()
            print("Admin created successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_initial_admin()