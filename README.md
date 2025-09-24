# HandMade – 手工展示管理系统

一个基于 **Flask + SQLite** 开发的轻量级手工艺品展示与后台管理系统。
支持前台分类展示，后台项目管理、图片上传与管理员管理。

---

## ✨ 功能特性

### 前台展示

* 首页分为 **针织类** 和 **手工类** 两大分类，默认展示4个，可点击对应分类查看全部
* 展示图片支持缩略图显示，默认进行压缩，加强浏览流畅度，点击后放大查看原图
* 自适应布局，兼容 **手机 / PC**
* 页面背景图静态展示，但保留 **PHP API 接口** ，可以动态获取，同时区别PC和Mobile


### 管理后台

* **管理员登录**：支持多管理员账户（暂未设置删除）
* **管理面板**：

  * 更新项目（分类 / 标题 / 描述 / 完成日期 / 图片上传）
  * 更新项目状态：制作中 / 排队中 / 已完成
  * 上传 / 替换项目成品图片
  * 已完成项目均会放到已完成项目中，增强管理面板的简洁度。
* **图片上传**：

  * 自动生成缩略图
  * 点击缩略图可放大查看原图
* **管理员管理**：

  * 支持新增管理员账户

---

## 🛠 技术栈

* **后端框架**：Flask (Python)
* **数据库**：SQLite （大数据可使用Mysql等数据库代替）
* **前端模板**：Jinja2 + HTML5 + CSS3
* **图片存储**：本地存储
* **部署**：Gunicorn + systemd + Nginx（可选）
* **安全**：管理员密码采用 `pbkdf2:sha256` 哈希存储

---

## 📂 目录结构

```
handmade/
├─ app.py              # Flask 主程序
├─ init_db.py          # 数据库初始化脚本
├─ project.py          # 项目相关逻辑
├─ handcraft.py        # 手工模块逻辑
├─ requirements.txt    # 依赖文件
├─ static/             # 静态资源
│   ├─ uploads/        # 原图上传目录
│   │   └─thumbnail    # 缩略图保存目录
│   └─ css/
│       └─ style.css
└─ templates/          # 前端模板
    ├─ base.html
    ├─ index.html
    ├─ login.html
    ├─ dashboard.html
    ├─ add_project.html
    ├─ completed_project.html
    ├─ categort.html
    ├─ add_admin.html
    └─ edit_project.html
```

---

## 🚀 部署与运行

### 1. 修改部分内容

运行前需修改以下参数（均在`app.py`）：

```python
app = Flask(__name__)
app.secret_key = 'xxxxxx # 修改为你自己的secret_key
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SERVER_NAME'] = 'xxx.xxx.xxx' #修改为你自己的域名 
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 启动服务（开发模式）

```bash
python app.py
```

访问：`http://0.0.0.0:5000`

### 5. 生产环境部署（Gunicorn + systemd）

```bash
venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

### 6. 可选配置（CSP）

在`base.html`中有CSP的相关配置，默认注释掉了，如果仅需要在公网通过`SERVER_NAME`访问，可选择取消注释，如下所示。

```html
<!-- 内容安全策略 -->
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; default-src https: 'self' 'unsafe-inline' 'unsafe-eval' data: blob:;">
```

取消注释后，通过非`SERVER_NAME`访问会导致CSS无法正确加载。


推荐结合 **Nginx 反向代理** 和 **HTTPS** 部署。

---

## 📷 功能（示例）

**演示站点**：https://hand.aimeisoul.serv00.net

（demo用户名：admin）
（demo密码：sAk\_!r=H1sd）

---

## 🔑 管理员功能

* 默认初始化时需手动插入一个管理员账户（默认密码admin123）：

```sql
INSERT INTO admin (username, password) VALUES ('admin', 'pbkdf2:sha256:admin123');
```

* 登录后可在后台继续添加新管理员。

---

## 📜 License

MIT License.
