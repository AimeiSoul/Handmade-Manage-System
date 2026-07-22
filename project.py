import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image

class Project:
    # 默认图片路径
    DEFAULT_IMAGE = 'undo.png'
    
    def __init__(self, id=None, title=None, description=None, category=None, status=None, image_path=None, created_at=None, completed_at=None, thumbnail_path=None, duration_days=None , stars=None):
        self.id = id
        self.title = title
        self.description = description
        self.category = category
        self.status = status
        # 如果没有提供图片路径，使用默认图片
        self.image_path = image_path if image_path else self.DEFAULT_IMAGE
        self.created_at = self._parse_datetime(created_at)
        self.completed_at = self._parse_datetime(completed_at)
        self.thumbnail_path = thumbnail_path if thumbnail_path else self.DEFAULT_IMAGE
        self.duration_days = duration_days
        self.stars = stars
    
    def _parse_datetime(self, dt_value):
        """将日期时间值转换为 datetime 对象"""
        if dt_value is None:
            return None
        
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            # 尝试解析多种日期时间格式
            formats = [
                '%Y-%m-%d',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(dt_value.strip(), fmt)
                except ValueError:
                    continue
        
        # 如果无法解析，返回原始值
        return dt_value

    @classmethod
    def get_all(cls, category=None):
        conn = sqlite3.connect('handshop.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT * FROM projects 
                WHERE category=?
                ORDER BY 
                    CASE status 
                        WHEN '制作中' THEN 0
                        WHEN '排队中' THEN 1
                        WHEN '已完成' THEN 2
                        ELSE 3
                    END,
                    CASE 
                        WHEN status = '已完成' AND completed_at IS NOT NULL THEN completed_at
                        ELSE created_at
                    END DESC
            ''', (category,))
        else:
            cursor.execute('''
                SELECT * FROM projects 
                ORDER BY 
                    CASE status 
                        WHEN '制作中' THEN 0
                        WHEN '排队中' THEN 1
                        WHEN '已完成' THEN 2
                        ELSE 3
                    END,
                    CASE 
                        WHEN status = '已完成' AND completed_at IS NOT NULL THEN completed_at
                        ELSE created_at
                    END DESC
            ''')
        
        projects = []
        for row in cursor.fetchall():
            p = cls()
            p.id = row['id']
            p.title = row['title']
            p.description = row['description']
            p.category = row['category']
            p.status = row['status']
            p.image_path = row['image_path']
            p.thumbnail_path = row['thumbnail_path']
            p.created_at = row['created_at']
            p.completed_at = row['completed_at']
            p.duration_days = row['duration_days'] if 'duration_days' in row.keys() else None
            p.stars = row['stars'] if 'stars' in row.keys() else None
            
            projects.append(p)
        
        conn.close()
        return projects
    
    @classmethod
    def init_likes_table(cls):
        """初始化点赞防刷记录表"""
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                client_token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        conn.close()

    @classmethod
    def toggle_like(cls, project_id, client_token):
        conn = sqlite3.connect('handshop.db', timeout=3.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 1. 检查项目是否存在
            cursor.execute('SELECT id, stars FROM projects WHERE id = ?', (project_id,))
            project = cursor.fetchone()
            if not project:
                return None, 0
            
            current_stars = project['stars'] if project['stars'] is not None else 0

            # 2. 检查是否已经点过赞
            cursor.execute(
                'SELECT id FROM project_likes WHERE project_id = ? AND client_token = ?',
                (project_id, str(client_token))
            )
            existing_like = cursor.fetchone()

            if existing_like:
                cursor.execute(
                    'DELETE FROM project_likes WHERE project_id = ? AND client_token = ?', (project_id, str(client_token)))
                new_stars = max(0, current_stars - 1)
                cursor.execute('UPDATE projects SET stars = ? WHERE id = ?', (new_stars, project_id))
                conn.commit()
                return 'unliked', new_stars
            else:
                cursor.execute(
                    'INSERT INTO project_likes (project_id, client_token) VALUES (?, ?)', (project_id, str(client_token)))
                new_stars = current_stars + 1
                cursor.execute('UPDATE projects SET stars = ? WHERE id = ?', (new_stars, project_id))
                conn.commit()
                return 'liked', new_stars
        finally:
            conn.close()

    @classmethod
    def get_liked_project_ids(cls, client_token):
        if not client_token:
            return set()
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT project_id FROM project_likes WHERE client_token = ?', (str(client_token),))
        rows = cursor.fetchall()
        conn.close()

        return {row[0] for row in rows}

    @classmethod
    def get_by_id(cls, project_id):
        conn = sqlite3.connect('handshop.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects WHERE id=?', (project_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            p = cls(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                category=row['category'],
                status=row['status'],
                image_path=row['image_path'],
                created_at=row['created_at'],
                completed_at=row['completed_at'],
                thumbnail_path=row['thumbnail_path'],
                duration_days=row['duration_days'] if 'duration_days' in row.keys() else None,
                stars=row['stars'] if 'stars' in row.keys() else None
            )
            return p
        return None

    def save(self):
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
    
        # 1. 统一格式化为 YYYY-MM-DD 字符串
        completed_at_value = self.completed_at.strftime('%Y-%m-%d') if isinstance(self.completed_at, datetime) else self.completed_at
        created_at_value = self.created_at.strftime('%Y-%m-%d') if isinstance(self.created_at, datetime) else self.created_at

        # 清洗无效的 created_at（防止带入文件名等脏数据）
        if not created_at_value or '-' not in str(created_at_value) or len(str(created_at_value)) < 8:
            created_at_value = None

        # 2. 如果项目已完成且同时拥有创建和完成日期，计算整数天数
        duration_value = None
        if self.status == '已完成' and created_at_value and completed_at_value:
            try:
                d1 = datetime.strptime(str(created_at_value).split()[0], '%Y-%m-%d')
                d2 = datetime.strptime(str(completed_at_value).split()[0], '%Y-%m-%d')
                delta = d2 - d1
                duration_value = max(0, delta.days) # 保证天数非负整数
            except Exception as e:
                print(f"[ERROR] 计算用时失败: {e}")
                duration_value = 0

        if self.id:
            # UPDATE
            if created_at_value:
                cursor.execute('''
                    UPDATE projects 
                    SET title=?, description=?, category=?, status=?, image_path=?, thumbnail_path=?, 
                        created_at=?, completed_at=?, duration_days=?, stars=?
                    WHERE id=?
                ''', (self.title, self.description, self.category, self.status, self.image_path, self.thumbnail_path, 
                      created_at_value, completed_at_value, duration_value, self.stars, self.id))
            else:
                cursor.execute('''
                    UPDATE projects 
                    SET title=?, description=?, category=?, status=?, image_path=?, thumbnail_path=?, 
                        completed_at=?, duration_days=?, stars=?
                    WHERE id=?
                ''', (self.title, self.description, self.category, self.status, self.image_path, self.thumbnail_path, 
                      completed_at_value, duration_value, self.stars, self.id))
        else:
            # INSERT
            if created_at_value:
                cursor.execute('''
                    INSERT INTO projects (title, description, category, status, image_path, thumbnail_path, created_at, completed_at, duration_days, stars)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ''', (self.title, self.description, self.category, self.status, self.image_path, self.thumbnail_path, 
                       created_at_value, completed_at_value, duration_value, self.stars))
            else:
                cursor.execute('''
                    INSERT INTO projects (title, description, category, status, image_path, thumbnail_path, completed_at, duration_days, stars)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.title, self.description, self.category, self.status, self.image_path, self.thumbnail_path, 
                      completed_at_value, duration_value, self.stars))
    
        conn.commit()
        conn.close()
    
    def delete(self):
        if self.image_path and self.image_path != self.DEFAULT_IMAGE:
            file_path = os.path.join('static', self.image_path)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"删除图片文件时出错: {e}")
        
        if self.thumbnail_path and self.thumbnail_path != self.DEFAULT_IMAGE:
            thumb_path = os.path.join('static', self.thumbnail_path)
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception as e:
                print(f"删除压缩图时出错: {e}")

        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM projects WHERE id=?', (self.id,))
        conn.commit()
        conn.close()

    @staticmethod
    def allowed_file(filename):
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @classmethod
    def save_uploaded_file(cls, file):
        if file and cls.allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            new_filename = f"{uuid.uuid4().hex}.{ext}"
            save_dir = os.path.join('static', 'uploads')
            thumb_dir = os.path.join(save_dir, 'thumbnail')
            os.makedirs(save_dir, exist_ok=True)
            os.makedirs(thumb_dir, exist_ok=True)

            save_path = os.path.join(save_dir, new_filename)
            file.save(save_path)

            thumbnail_filename = f"thumb_{uuid.uuid4().hex}.webp"
            thumb_path = os.path.join(thumb_dir, thumbnail_filename)
            try:
                img = Image.open(save_path)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(thumb_path, "WEBP", quality=80, method=6)
            except Exception as e:
                print(f"生成压缩图时出错: {e}")
                thumbnail_filename = None

            return f'uploads/{new_filename}', f'uploads/thumbnail/{thumbnail_filename}'
        else:
            return cls.DEFAULT_IMAGE, cls.DEFAULT_IMAGE

    def format_completed_date(self):
        if not self.completed_at:
            return '---'
        if isinstance(self.completed_at, datetime):
            return self.completed_at.strftime('%Y年%m月%d日')
        parsed = self._parse_datetime(self.completed_at)
        return parsed.strftime('%Y年%m月%d日') if isinstance(parsed, datetime) else '---'

    def get_completed_date_for_input(self):
        if not self.completed_at:
            return ''
        if isinstance(self.completed_at, datetime):
            return self.completed_at.strftime('%Y-%m-%d')
        parsed = self._parse_datetime(self.completed_at)
        return parsed.strftime('%Y-%m-%d') if isinstance(parsed, datetime) else ''
            
    def format_created_date(self):
        if not self.created_at:
            return '---'
        if isinstance(self.created_at, datetime):
            return self.created_at.strftime('%Y年%m月%d日')
        parsed = self._parse_datetime(self.created_at)
        return parsed.strftime('%Y年%m月%d日') if isinstance(parsed, datetime) else '---'

    def get_created_date_for_input(self):
        if not self.created_at:
            return ''
        if isinstance(self.created_at, datetime):
            return self.created_at.strftime('%Y-%m-%d')
        parsed = self._parse_datetime(self.created_at)
        return parsed.strftime('%Y-%m-%d') if isinstance(parsed, datetime) else ''