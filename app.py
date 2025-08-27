from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from project import Project
from handcraft import Admin
import os
import random
import re
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
    x_for=1,  # 信任的代理层数
    x_proto=1,
    x_host=1,
    x_prefix=1
)

# 背景图片API
#BACKGROUND_API_PC = "https://api.sretna.cn/api/pc.php"
#BACKGROUND_API_MOBILE = "https://api.sretna.cn/api/pe.php"

# 设置会话永久性
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

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

# 首页视图
@app.route('/')
def home():
    #检查会话是否过期
    check_session_expiry()

    # 获取所有项目
    all_projects = Project.get_all()

    latest_projects = Project.get_all()[:4]

    return render_template('index.html', 
                          background=get_background(),
                          device_type=get_device_type(),
                          latest_projects=latest_projects)

# 分类视图
@app.route('/category/<category>')
def show_category(category):
    page = request.args.get("page", 1, type=int)  # 当前页码
    per_page = 6  # 每页项目数

    # 获取该分类下的所有项目
    projects = Project.get_all(category)
    total = len(projects)
    total_pages = ceil(total / per_page)

    # 取出当前页的数据
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
        total_pages=total_pages
    )

#检查会话是否过期
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
    return False

#会话检查点
@app.route('/check_session')
def check_session():
    if not check_session_expiry():
        return redirect(url_for('admin_login'))
    return '', 204

# 登录视图
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
            flash('登录成功','success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html', 
                          background=get_background(),
                          device_type=get_device_type())

# 登出视图
@app.route('/logout')
def admin_logout():
    session.clear()
    flash('已成功退出登录', 'success')
    return redirect(url_for('home'))

#检查登录状态的装饰器
def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_session_expiry():
            flash('登录已过期，请重新登录', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 管理面板视图
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

# 已完成项目列表视图
@app.route('/completed_projects')
@login_required
def completed_projects():
    page = request.args.get("page", 1, type=int)  # 当前页
    per_page = 8  # 每页8行

    # 获取已完成项目列表
    completed_projects_list = [p for p in Project.get_all() if p.status.strip() == '已完成']
    total = len(completed_projects_list)
    total_pages = ceil(total / per_page)

    # 取出当前页的数据
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


# 添加项目视图
@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_new_project():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description').strip()
        category = request.form['category']
        status = request.form['status']
        completed_at = request.form.get('completed_at')  # 获取完成时间（可能为空）
        
        project = Project()
        project.title = title
        project.description = description if description else None
        project.category = category
        project.status = status

       # 只有在状态为"已完成"且有填写完成时间时才保存
        if status == '已完成' and completed_at:
            # 确保日期格式正确
            try:
                # 将日期字符串转换为 datetime 对象
                date_obj = datetime.strptime(completed_at, '%Y-%m-%d')
                project.completed_at = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                # 如果日期格式无效，设置为 None
                project.completed_at = None
                flash('完成时间格式无效，已忽略', 'warning')
        else:
            project.completed_at = None
        
        # 处理文件上传
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                 image_path, thumbnail_path = Project.save_uploaded_file(file)
                 project.image_path = image_path
                 project.thumbnail_path = thumbnail_path
            else:
                project.image_path = Project.DEFAULT_IMAGE
                project.thumbnail_path = Project.DEFAULT_IMAGE
        # 如果没有文件上传字段，使用默认图片
        else:
            project.image_path = Project.DEFAULT_IMAGE
            project.thumbnail_path = Project.DEFAULT_IMAGE

        project.save()
        flash('项目添加成功', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_project.html', 
                          background=get_background(),
                          device_type=get_device_type())

# 编辑项目视图
@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_existing_project(project_id):
    project = Project.get_by_id(project_id)
    
    if not project:
        flash('项目不存在', 'error')
        return redirect(url_for('admin_dashboard'))
   
    if request.method == 'POST':
        old_image_path = project.image_path
        old_thumbnail_path = project.thumbnail_path

        project.title = request.form['title']
        project.description = request.form.get('description').strip()
        project.category = request.form['category']
        project.status = request.form['status']
        completed_at = request.form.get('completed_at')  # 获取完成时间（可能为空）

        # 只有在状态为"已完成"且有填写完成时间时才保存
        if project.status == '已完成' and completed_at:
            # 确保日期格式正确
            try:
                # 将日期字符串转换为 datetime 对象
                date_obj = datetime.strptime(completed_at, '%Y-%m-%d')
                project.completed_at = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                # 如果日期格式无效，设置为 None
                project.completed_at = None
                flash('完成时间格式无效，已忽略', 'warning')
        else:
            project.completed_at = None

        # 处理文件上传
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                if old_image_path and old_image_path != Project.DEFAULT_IMAGE:
                    old_file_path = os.path.join('static', old_image_path)
                    try:
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                            print(f"已删除旧图片: {old_file_path}")
                    except Exception as e:
                        print(f"删除旧图片时出错: {e}")

                if old_thumbnail_path and old_thumbnail_path != Project.DEFAULT_IMAGE:
                    old_thumb_path = os.path.join('static', old_thumbnail_path)
                    if os.path.exists(old_thumb_path):
                        os.remove(old_thumb_path)
                        print(f"已删除旧缩略图: {old_thumb_path}")

                #保存新照片
                image_path, thumbnail_path = Project.save_uploaded_file(file)
                project.image_path = image_path
                project.thumbnail_path = thumbnail_path
            else:
                project.image_path = old_image_path
                project.thumbnail_path = old_thumbnail_path
        
        project.save()
        flash('项目更新成功', 'success')

        # 根据 status 判断跳转页面
        if project.status == '已完成':
            return redirect(url_for('completed_projects'))  # 假设路由名为 completed_projects
        else:
            return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_project.html', 
                          project=project, 
                          background=get_background(),
                          device_type=get_device_type())

# 删除项目视图
@app.route('/delete_project/<int:project_id>')
@login_required
def delete_existing_project(project_id):
    project = Project.get_by_id(project_id)
    if project:
        project.delete()
        flash('项目已删除', 'success')
    return redirect(url_for('admin_dashboard'))

# 添加管理员视图
@app.route('/add_admin', methods=['GET', 'POST'])
@login_required
def add_new_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if Admin.create(username, password):
            flash('管理员添加成功', 'success')
        else:
            flash('用户名已存在', 'error')
    
    admins = Admin.get_all()
    return render_template('add_admin.html', 
                          admins=admins, 
                          background=get_background(),
                          device_type=get_device_type())

#每次请求前检查会话
@app.before_request
def before_request():
    if session.get('_last_activity'):
       session['_last_activity'] = datetime.now().isoformat()

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0',port=5000,debug=True)
