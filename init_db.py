import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    conn = sqlite3.connect('handshop.db')
    cursor = conn.cursor()

    # 创建项目表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        status TEXT NOT NULL,
        image_path TEXT,
        thumbnail_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP NULL
    )
    ''')

    # 创建管理员表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 添加默认管理员
    try:
        cursor.execute(
            'INSERT INTO admins (username, password_hash) VALUES (?, ?)',
            ('admin', generate_password_hash('admin123'))
        )
    except sqlite3.IntegrityError:
        pass  # 管理员已存在

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
