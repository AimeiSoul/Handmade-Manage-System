from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.middleware.proxy_fix import ProxyFix
from project import Project
from handcraft import Admin
import os
import random
import re
import uuid
from math import ceil
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sercet_key_here'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

# 配置HTTPS（在反向代理后运行时需要）
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SERVER_NAME'] = 'handmade.domain.com'  # 替换为您的域名

# 处理反向代理
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,   # 信任的代理层数
    x_proto=1,
    x_host=1,
    x_prefix=1
)

# 设置会话永久性（1天）
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

# 🔑 1. 把迁移函数放在这里
def migrate_duration_days():
    import sqlite3
    from datetime import datetime
    try:
        conn = sqlite3.connect('handshop.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # 查找所有状态为已完成，但 duration_days 为空的数据
        cursor.execute("SELECT id, created_at, completed_at FROM projects WHERE status='已完成' AND (duration_days IS NULL)")
        rows = cursor.fetchall()
        
        count = 0
        for row in rows:
            if row['created_at'] and row['completed_at']:
                try:
                    d1 = datetime.strptime(row['created_at'].split()[0], '%Y-%m-%d')
                    d2 = datetime.strptime(row['completed_at'].split()[0], '%Y-%m-%d')
                    days = max(0, (d2 - d1).days)
                    cursor.execute("UPDATE projects SET duration_days = ? WHERE id = ?", (days, row['id']))
                    count += 1
                except Exception:
                    pass
        conn.commit()
        conn.close()
        if count > 0:
            print(f"[INFO] 成功自动迁移并计算了 {count} 个已完成项目的历史天数！")
    except Exception as e:
        print(f"[ERROR] 迁移用时字段失败: {e}")

# 🔑 2. 在 Flask 首次运行请求前或启动时调用一次
with app.app_context():
    migrate_duration_days()
    Project.init_likes_table()

# ==========================================================================
# 1. Miku 主题与全局上下文注入 (Context Processors)
# ==========================================================================
@app.context_processor
def inject_miku_theme():
    """
    自动向所有 Jinja2 模板注入 Miku 主题的全局信息，
    无需在每个 render_template 中重复编写
    """
    return {
        'miku_theme': {
            'primary': '#39C5BB',      # 经典葱绿 (Miku Green)
            'primary_dark': '#2EB0A6', # 深葱绿
            'accent': '#FF007F',       # 经典发饰粉 (Magenta Pink)
            'version': '39-Style'
        },
        'current_year': datetime.now().year
    }

# 获取设备类型
def get_device_type():
    """根据User-Agent判断设备类型"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['iphone', 'android', 'ipod', 'ipad', 'mobile', 'blackberry', 'opera mini', 'windows phone']
    return 'mobile' if any(keyword in user_agent for keyword in mobile_keywords) else 'desktop'

# 获取背景图片(路径static/)
def get_background():
    """根据设备类型获取不同的背景图"""
    device = get_device_type()
    if device == 'mobile':
        return url_for('static', filename='pe.jpg')
    else:
        return url_for('static', filename='pc.jpg')

# 检查会话是否过期
def check_session_expiry():
    if 'admin' in session:
        if session.permanent:
            last_activity = session.get('_last_activity')
            if last_activity:
                last_activity = datetime.fromisoformat(last_activity)
                if datetime.now() - last_activity > app.config['PERMANENT_SESSION_LIFETIME']:
                    session.clear()
                    return False
            session['_last_activity'] = datetime.now().isoformat()
        return True
    return True

# 检查登录状态的装饰器
def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_session_expiry():
            flash('登录已过期，请重新登录 (登录超时)', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 每次请求前更新最后活动时间
@app.before_request
def before_request():
    if session.get('_last_activity'):
        session['_last_activity'] = datetime.now().isoformat()

# ==========================================================================
# 2. 路由视图函数 (Routes)
# ==========================================================================

# 首页视图
@app.route('/')
def home():
    check_session_expiry()
    client_token = request.cookies.get('client_token')
    liked_project_ids = Project.get_liked_project_ids(client_token)
    all_projects = Project.get_all()
    latest_projects = all_projects[:4]

    return render_template('index.html', 
                           background=get_background(),
                           device_type=get_device_type(),
                           latest_projects=latest_projects,
                           liked_project_ids=liked_project_ids)

# 分类视图
@app.route('/category/<category>')
def show_category(category):
    client_token = request.cookies.get('client_token')
    liked_project_ids = Project.get_liked_project_ids(client_token)
    page = request.args.get("page", 1, type=int)
    per_page = 6

    projects = Project.get_all(category)
    total = len(projects)
    total_pages = ceil(total / per_page)

    start = (page - 1) * per_page
    end = start + per_page
    projects_paginated = projects[start:end]

    return render_template(
        'category.html',
        category=category,
        projects=projects_paginated,
        background=get_background(),
        device_type=get_device_type(),
        page=page,
        total_pages=total_pages,
        liked_project_ids=liked_project_ids,
    )

# 会话在线探针/检查点
@app.route('/check_session')
def check_session():
    if not check_session_expiry():
        return redirect(url_for('admin_login'))
    return '', 204

# 管理员登录
@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if Admin.verify_password(username, password):
            session['admin'] = username
            session.permanent = True
            session['login_time'] = datetime.now().isoformat()
            session['_last_activity'] = datetime.now().isoformat()
            flash('欢迎回来！身份验证成功 ♪', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误，请重新输入', 'error')
    
    return render_template('login.html', 
                           background=get_background(),
                           device_type=get_device_type())

# 登出
@app.route('/logout')
def admin_logout():
    session.clear()
    flash('已安全退出控制台', 'success')
    return redirect(url_for('home'))

# 管理控制面板
@app.route('/dashboard')
@login_required
def admin_dashboard():
    knitting_projects = [p for p in Project.get_all('knitting') if p.status != '已完成']
    crafting_projects = [p for p in Project.get_all('crafting') if p.status != '已完成']

    return render_template('dashboard.html', 
                           knitting_projects=knitting_projects,
                           crafting_projects=crafting_projects,
                           background=get_background(),
                           device_type=get_device_type())

# 已完成项目展示列表
@app.route('/completed_projects')
@login_required
def completed_projects():
    page = request.args.get("page", 1, type=int)
    per_page = 8

    completed_projects_list = [p for p in Project.get_all() if p.status.strip() == '已完成']
    total = len(completed_projects_list)
    total_pages = ceil(total / per_page)

    start = (page - 1) * per_page
    end = start + per_page
    projects_paginated = completed_projects_list[start:end]

    return render_template(
        'completed_projects.html',
        projects=projects_paginated,
        background=get_background(),
        device_type=get_device_type(),
        page=page,
        total_pages=total_pages
    )

# 添加新项目
@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_new_project():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '').strip()
        category = request.form['category']
        status = request.form['status']
        status_date = request.form.get('completed_at') 
        
        project = Project()
        project.title = title
        project.description = description if description else None
        project.category = category
        project.status = status

        parsed_date = None
        if status_date:
            try:
                date_obj = datetime.strptime(status_date.strip(), '%Y-%m-%d')
                parsed_date = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                flash('时间格式无效，已忽略', 'warning')

        today_str = datetime.now().strftime('%Y-%m-%d')
        target_date = parsed_date if parsed_date else today_str

        if status == '制作中':
            project.created_at = target_date  # 写入开工时间
            project.completed_at = None
        elif status == '已完成':
            project.completed_at = target_date # 写入完成时间
        else: # 排队中
            project.completed_at = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                image_path, thumbnail_path = Project.save_uploaded_file(file)
                project.image_path = image_path
                project.thumbnail_path = thumbnail_path
            else:
                project.image_path = Project.DEFAULT_IMAGE
                project.thumbnail_path = Project.DEFAULT_IMAGE
        else:
            project.image_path = Project.DEFAULT_IMAGE
            project.thumbnail_path = Project.DEFAULT_IMAGE

        project.save()
        flash('项目创建成功！', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_project.html', 
                           background=get_background(),
                           device_type=get_device_type())


# 编辑项目
@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_existing_project(project_id):
    project = Project.get_by_id(project_id)
    
    if not project:
        flash('未寻找到该项目记录', 'error')
        return redirect(url_for('admin_dashboard'))
   
    if request.method == 'POST':
        old_image_path = project.image_path
        old_thumbnail_path = project.thumbnail_path

        project.title = request.form['title']
        project.description = request.form.get('description', '').strip()
        project.category = request.form['category']
        project.status = request.form['status']
        status_date = request.form.get('completed_at')

        # 🔑 解析日期格式
        parsed_date = None
        if status_date:
            try:
                date_obj = datetime.strptime(status_date.strip(), '%Y-%m-%d')
                parsed_date = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                flash('时间格式无效，已忽略', 'warning')

        # 🔑 默认兜底：如果进入制作中/已完成但没有有效日期，采用今天
        today_str = datetime.now().strftime('%Y-%m-%d')
        target_date = parsed_date if parsed_date else today_str

        # 🔑 根据不同状态更新对应的数据库字段
        if project.status == '制作中':
            project.created_at = target_date  # 将新选日期写到 created_at
            project.completed_at = None       # 清空 completed_at
        elif project.status == '已完成':
            project.completed_at = target_date # 写到 completed_at
        else: # 排队中
            project.completed_at = None       # 清空 completed_at

        # 处理图片更新逻辑
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                # 清理旧图片资源
                if old_image_path and old_image_path != Project.DEFAULT_IMAGE:
                    old_file_path = os.path.join('static', old_image_path)
                    try:
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    except Exception as e:
                        print(f"删除旧图片出错: {e}")

                if old_thumbnail_path and old_thumbnail_path != Project.DEFAULT_IMAGE:
                    old_thumb_path = os.path.join('static', old_thumbnail_path)
                    if os.path.exists(old_thumb_path):
                        os.remove(old_thumb_path)

                # 保存新上传的文件
                image_path, thumbnail_path = Project.save_uploaded_file(file)
                project.image_path = image_path
                project.thumbnail_path = thumbnail_path
            else:
                project.image_path = old_image_path
                project.thumbnail_path = old_thumbnail_path
        
        project.save()
        flash('项目更新成功！', 'success')

        if project.status == '已完成':
            return redirect(url_for('completed_projects'))
        else:
            return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_project.html', 
                           project=project, 
                           background=get_background(),
                           device_type=get_device_type())

# 删除项目
@app.route('/delete_project/<int:project_id>')
@login_required
def delete_existing_project(project_id):
    project = Project.get_by_id(project_id)
    if project:
        project.delete()
        flash('项目已彻底清理', 'success')
    return redirect(url_for('admin_dashboard'))

# 添加新管理员
@app.route('/add_admin', methods=['GET', 'POST'])
@login_required
def add_new_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if Admin.create(username, password):
            flash('新管理员账号添加成功', 'success')
        else:
            flash('用户名已存在，请换一个名称', 'error')
    
    admins = Admin.get_all()
    return render_template('add_admin.html', 
                           admins=admins, 
                           background=get_background(),
                           device_type=get_device_type())

@app.route('/project/<int:project_id>/like', methods=['POST'])
def toggle_like(project_id):
    # 1. 获取或生成浏览器的唯一标识 Cookie (client_token)
    client_token = request.cookies.get('client_token')
    is_new_token = False
    if not client_token:
        client_token = uuid.uuid4().hex
        is_new_token = True

    # 2. 调用 Project 模型中封装好的点赞方法
    action, stars_count = Project.toggle_like(project_id, client_token)

    if action is None:
        return jsonify({'success': False, 'message': '项目不存在'}), 404

    message = '点赞成功！❤️' if action == 'liked' else '已取消点赞~'

    response = jsonify({
        'success': True, 
        'action': action,
        'message': message, 
        'stars': stars_count
    })

    if is_new_token:
        response.set_cookie(
            'client_token', 
            client_token, 
            max_age=60*60*24*365,
            httponly=True, 
            samesite='Lax'
        )
    
    return response

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=True)