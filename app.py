from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect
from admin import Admin
import os
import uuid
import filetype


# ---------- Основная настройка ----------
basedir = os.path.abspath(os.path.dirname(__file__))
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SECRET_KEY'] = Admin.session_token
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 МБ на запрос

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIMES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}

csrf = CSRFProtect()
csrf.init_app(app)

db = SQLAlchemy(app)


# ---------- Таблицы БД ----------

class Posts(db.Model):
    post_id = db.Column(db.Integer, primary_key=True)
    post_title = db.Column(db.String(100), nullable=False)
    post_text = db.Column(db.Text, nullable=False)
    post_date = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship('PostImage', backref='post', cascade='all, delete-orphan')

    def __repr__(self):
        return '<Posts %r>' % self.post_id


class PostImage(db.Model):
    img_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.post_id'), nullable=False)
    img_name = db.Column(db.String(255), nullable=False)
    img_type = db.Column(db.String(10), nullable=False, default='foreign')

    def __repr__(self):
        return '<PostImage %r>' % self.img_id


class MainData(db.Model):
    main_data_id = db.Column(db.Integer, primary_key=True)
    data_name = db.Column(db.String(100), nullable=False, unique=True)
    data_value = db.Column(db.String(255), nullable=False)
    data_link = db.Column(db.String(255), nullable=True)
    is_link = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return '<MainData %r>' % self.main_data_id


# ---------- Вспомогательные функции ----------

@app.context_processor
def inject_auth():
    return dict(auth=is_auth())


def is_auth():
    return session.get('auth') is True


def save_image(file):
    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(path)
    return unique_name


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_allowed_mime(file_storage):
    header = file_storage.read(1024)
    file_storage.seek(0)
    kind = filetype.guess(header)
    if kind is None:
        return False
    return kind.mime in ALLOWED_MIMES


def remove_file_silently(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('auth') is not True:
            return redirect('/')
        return f(*args, **kwargs)
    return wrapper


# ---------- О нас / Main Data ----------

@app.route('/about')
def about():
    main_data = MainData.query.all()
    return render_template('about.html', main_data=main_data)


@app.route('/main-data-management', methods=['GET', 'POST'])
@login_required
def main_data_management():
    main_data = MainData.query.all()

    if not main_data:
        new_main_data = MainData(
            data_name='default',
            data_value='default',
            is_link=False,
            data_link='',
        )
        db.session.add(new_main_data)
        db.session.commit()
        main_data = MainData.query.all()

    if request.method == 'POST':
        for row in main_data:
            sid = row.main_data_id
            row.data_name = request.form.get(f'data_name{sid}', row.data_name)
            row.data_value = request.form.get(f'data_value{sid}', row.data_value or '')
            row.data_link = request.form.get(f'data_link{sid}', row.data_link or '')
            row.is_link = f'is_link{sid}' in request.form

        db.session.commit()
        flash('Настройки обновлены', 'success')
        return redirect('/about')

    return render_template('main_data_management.html', main_data=main_data)


@app.route('/add-main-data', methods=['GET', 'POST'])
@login_required
def add_main_data():
    if request.method == 'POST':
        new_data_name = request.form.get('data_name_new', '').strip()
        new_data_value = request.form.get('data_value_new', '').strip()
        new_data_link = request.form.get('data_link_new', '').strip()
        new_is_link = 'is_link_new' in request.form

        if not new_data_name:
            flash('Укажите название', 'danger')
            return redirect(url_for('add_main_data'))

        if MainData.query.filter_by(data_name=new_data_name).first():
            flash('Такая настройка уже есть', 'danger')
            return redirect(url_for('add_main_data'))

        new_main_data = MainData(
            data_name=new_data_name,
            data_value=new_data_value,
            is_link=new_is_link,
            data_link=new_data_link,
        )
        db.session.add(new_main_data)
        db.session.commit()
        return redirect('/main-data-management')

    return render_template('add_main_data.html')


@app.route('/delete-main-data/<int:main_data_id>', methods=['POST'])
@login_required
def delete_main_data(main_data_id):
    main_data = MainData.query.get_or_404(main_data_id)
    db.session.delete(main_data)
    db.session.commit()
    return redirect('/main-data-management')


# ---------- Посты ----------

@app.route('/')
@app.route('/posts')
@app.route('/posts/<int:page>')
def posts(page=1):
    per_page = 8
    pagination = Posts.query.order_by(Posts.post_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template('posts.html', posts=pagination.items, pagination=pagination)


@app.route('/posts/detail/<int:post_id>')
def post_detail(post_id):
    post = Posts.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)


@app.route('/create-post', methods=['POST', 'GET'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('post_title', '').strip()
        text = request.form.get('post_text', '').strip()

        if not title:
            flash('Заголовок не может быть пустым', 'danger')
            return redirect('/create-post')
        if len(title) > 100:
            flash('Заголовок слишком длинный (макс. 100)', 'danger')
            return redirect('/create-post')

        post = Posts(post_title=title, post_text=text)
        db.session.add(post)
        db.session.flush()   # получаем post.post_id

        # --- главная картинка ---
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '':
            if not allowed_file(main_file.filename):
                flash(f'Файл {main_file.filename}: недопустимое расширение', 'danger')
            elif not is_allowed_mime(main_file):
                flash(f'Файл {main_file.filename}: не является изображением', 'danger')
            else:
                unique_name = save_image(main_file)
                db.session.add(PostImage(
                    post_id=post.post_id,
                    img_name=unique_name,
                    img_type='primary',
                ))

        # --- дополнительные картинки ---
        for file in request.files.getlist('secondary_images'):
            if not file or file.filename == '':
                continue
            if not allowed_file(file.filename):
                flash(f'Файл {file.filename}: недопустимое расширение', 'danger')
            elif not is_allowed_mime(file):
                flash(f'Файл {file.filename}: не является изображением', 'danger')
            else:
                unique_name = save_image(file)
                db.session.add(PostImage(
                    post_id=post.post_id,
                    img_name=unique_name,
                    img_type='foreign',
                ))

        db.session.commit()
        return redirect('/posts')

    return render_template('create_post.html')


@app.route('/edit-post/<int:post_id>', methods=['POST', 'GET'])
@login_required
def edit_post(post_id):
    post = Posts.query.get_or_404(post_id)

    if request.method == 'POST':
        # 1. текст
        title = request.form.get('post_title', '').strip()
        text = request.form.get('post_text', '').strip()

        if not title:
            flash('Заголовок не может быть пустым', 'danger')
            return redirect(url_for('edit_post', post_id=post_id))
        if len(title) > 100:
            flash('Заголовок слишком длинный (макс. 100)', 'danger')
            return redirect(url_for('edit_post', post_id=post_id))

        post.post_title = title
        post.post_text = text

        # 2. замена главной
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '':
            if not allowed_file(main_file.filename):
                flash(f'Файл {main_file.filename}: недопустимое расширение', 'danger')
            elif not is_allowed_mime(main_file):
                flash(f'Файл {main_file.filename}: не является изображением', 'danger')
            else:
                unique_name = save_image(main_file)
                old_primary = PostImage.query.filter_by(
                    post_id=post_id, img_type='primary'
                ).first()
                if old_primary:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_primary.img_name)
                    remove_file_silently(old_path)
                    db.session.delete(old_primary)

                db.session.add(PostImage(
                    post_id=post_id,
                    img_name=unique_name,
                    img_type='primary',
                ))

        # 3. удаление отмеченных
        for img_id in request.form.getlist('delete_images'):
            try:
                img_id = int(img_id)
            except (ValueError, TypeError):
                continue
            img = PostImage.query.get(img_id)
            if img and img.post_id == post_id and img.img_type != 'primary':
                path = os.path.join(app.config['UPLOAD_FOLDER'], img.img_name)
                remove_file_silently(path)
                db.session.delete(img)

        # 4. добавление новых
        for file in request.files.getlist('secondary_images'):
            if not file or file.filename == '':
                continue
            if not allowed_file(file.filename):
                flash(f'Файл {file.filename}: недопустимое расширение', 'danger')
            elif not is_allowed_mime(file):
                flash(f'Файл {file.filename}: не является изображением', 'danger')
            else:
                unique_name = save_image(file)
                db.session.add(PostImage(
                    post_id=post_id,
                    img_name=unique_name,
                    img_type='foreign',
                ))

        db.session.commit()
        return redirect(url_for('post_detail', post_id=post_id))

    return render_template('edit_post.html', post=post)


@app.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Posts.query.get_or_404(post_id)

    for img in post.images:
        path = os.path.join(app.config['UPLOAD_FOLDER'], img.img_name)
        remove_file_silently(path)

    db.session.delete(post)
    db.session.commit()

    flash('Пост удалён', 'success')
    return redirect(url_for('posts'))


# ---------- Админка ----------

@app.route(f'/{Admin.admin_pannel_url}', methods=['POST', 'GET'])
def admin():
    if request.method == 'POST':
        login = request.form.get('login', '')
        password = request.form.get('password', '')

        if login == Admin.login and check_password_hash(Admin.password_hash, password):
            csrf_token_value = session.get('csrf_token')
            session.clear()
            if csrf_token_value:
                session['csrf_token'] = csrf_token_value
            session['auth'] = True
            return redirect('/success_auth')

        session.pop('auth', None)
        flash('Неверный логин или пароль', 'danger')

    return render_template('admin.html')


@app.route('/success_auth')
@login_required
def success_auth():
    return render_template('success_auth.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------- Ошибки ----------

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(413)
def too_large(error):
    flash('Файл слишком большой (макс. 5 МБ на запрос)', 'danger')
    return redirect(request.referrer or '/'), 413


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('404.html'), 500


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)