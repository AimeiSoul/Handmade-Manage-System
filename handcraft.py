import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

class Admin:
    @staticmethod
    def get_by_username(username):
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins WHERE username=?', (username,))
        row = cursor.fetchone()
        conn.close()
        return row if row else None

    @staticmethod
    def create(username, password):
        password_hash = generate_password_hash(password)
        try:
            conn = sqlite3.connect('handshop.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO admins (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # 用户名已存在
        finally:
            conn.close()

    @staticmethod
    def verify_password(username, password):
        admin = Admin.get_by_username(username)
        if admin:
            return check_password_hash(admin[2], password)
        return False

    @staticmethod
    def get_all():
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins')
        admins = cursor.fetchall()
        conn.close()
        return admins
