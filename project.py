import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image

class Project:
    # 默认图片路径
    DEFAULT_IMAGE = 'undo.png'
    
    def __init__(self, id=None, title=None, description=None, category=None, status=None, image_path=None, created_at=None, completed_at=None, thumbnail_path=None):
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
    
    def _parse_datetime(self, dt_value):
        """将日期时间值转换为 datetime 对象"""
        if dt_value is None:
            return None
        
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            # 尝试解析多种日期时间格式
            formats = [
                '%Y-%m-%d %H:%M:%S',  # SQLite 默认格式
                '%Y-%m-%d',            # 只有日期
                '%Y-%m-%d %H:%M',      # 日期和时间（没有秒）
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(dt_value, fmt)
                except ValueError:
                    continue
        
        # 如果无法解析，返回原始值
        return dt_value

    @classmethod
    def get_all(cls, category=None):
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        
        if category:
            # 使用复杂的CASE语句处理排序
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
            # 使用复杂的CASE语句处理排序
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
            projects.append(cls(*row))
        
        conn.close()
        return projects

    @classmethod
    def get_by_id(cls, project_id):
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects WHERE id=?', (project_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return cls(*row)
        return None

    def save(self):
        conn = sqlite3.connect('handshop.db')
        cursor = conn.cursor()
        
        # 准备要保存的值
        completed_at_value = self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.completed_at, datetime) else self.completed_at
        
        if self.id:
            cursor.execute('''
                UPDATE projects 
                SET title=?, description=?, category=?, status=?, image_path=?, completed_at=?, thumbnail_path=?
                WHERE id=?
            ''', (self.title, self.description, self.category, self.status, self.image_path, completed_at_value, self.thumbnail_path, self.id))
        else:
            cursor.execute('''
                INSERT INTO projects (title, description, category, status, image_path, completed_at, thumbnail_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (self.title, self.description, self.category, self.status, self.image_path, completed_at_value, self.thumbnail_path))
        
        conn.commit()
        conn.close()
    
    def delete(self):
        # 删除关联的图片文件（如果不是默认图片）
        if self.image_path and self.image_path != self.DEFAULT_IMAGE:
            # 构建完整的文件路径
            file_path = os.path.join('static', self.image_path)
            try:
                # 检查文件是否存在
                if os.path.exists(file_path):
                    # 删除文件
                    os.remove(file_path)
                    print(f"已删除图片文件: {file_path}")
            except Exception as e:
                print(f"删除图片文件时出错: {e}")
        
        # 删除缩略图
        if self.thumbnail_path and self.thumbnail_path != self.DEFAULT_IMAGE:
            thumb_path = os.path.join('static', self.thumbnail_path)
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
                    print(f"已删除缩略图文件: {thumb_path}")
            except Exception as e:
                print(f"删除缩略图时出错: {e}")

        # 删除数据库记录
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
             # 使用 UUID 生成唯一文件名
            ext = file.filename.rsplit('.', 1)[1].lower()
            new_filename = f"{uuid.uuid4().hex}.{ext}"
            save_dir = os.path.join('static', 'uploads')
            thumb_dir = os.path.join(save_dir, 'thumbnail')
            os.makedirs(save_dir, exist_ok=True)
            os.makedirs(thumb_dir, exist_ok=True)

            # 保存原图
            save_path = os.path.join(save_dir, new_filename)
            file.save(save_path)

            # 生成缩略图
            thumbnail_filename = f"thumb_{new_filename}"
            thumb_path = os.path.join(thumb_dir, thumbnail_filename)
            try:
                img = Image.open(save_path)
                img.thumbnail((300, 300))  # 设置缩略图最大尺寸
                img.save(thumb_path)
                return f'uploads/{new_filename}', f'uploads/thumbnail/{thumbnail_filename}'
            except Exception as e:
                print(f"生成缩略图出错: {e}")
                # 如果缩略图失败，就返回默认缩略图
                return f'uploads/{new_filename}', cls.DEFAULT_IMAGE
        else:
            # 没有上传文件，返回默认图片和缩略图
            return cls.DEFAULT_IMAGE, cls.DEFAULT_IMAGE

    def format_completed_date(self):
        """格式化完成时间显示"""
        if not self.completed_at:
            return '---'
        
        if isinstance(self.completed_at, datetime):
            return self.completed_at.strftime('%Y年%m月%d日')
        else:
            # 如果 completed_at 不是 datetime 对象，尝试解析
            parsed = self._parse_datetime(self.completed_at)
            if isinstance(parsed, datetime):
                return parsed.strftime('%Y年%m月%d日')
            else:
                return '---'

    def get_completed_date_for_input(self):
        """返回用于input[type=date]的完成时间字符串（YYYY-MM-DD格式）"""
        if not self.completed_at:
            return ''
        
        if isinstance(self.completed_at, datetime):
            return self.completed_at.strftime('%Y-%m-%d')
        else:
            # 如果 completed_at 不是 datetime 对象，尝试解析
            parsed = self._parse_datetime(self.completed_at)
            if isinstance(parsed, datetime):
                return parsed.strftime('%Y-%m-%d')
            else:
                return ''
