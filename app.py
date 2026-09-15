from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from functools import wraps
from admin import Admin

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SECRET_KEY'] = '[.cMPq|cZSneIgmOBT8kBQax-}D+Y6!%'
db = SQLAlchemy(app)

app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 МБ на запрос
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

#------- Таблицы БД -------
class Article(db.Model):
    article_id = db.Column(db.Integer, primary_key=True)
    article_title = db.Column(db.String(100), nullable=False)
    article_text = db.Column(db.Text, nullable=False)
    article_date = db.Column(db.DateTime, default=datetime.utcnow)

    # связь с картинками (не колонка в БД, а "виртуальное" поле)
    images = db.relationship('ArticleImage', backref='article', cascade='all, delete-orphan')

    def __repr__(self):
        return '<Article %r>' % self.article_id


class ArticleImage(db.Model):
	img_id = db.Column(db.Integer, primary_key=True)
	article_id = db.Column(db.Integer, db.ForeignKey('article.article_id'), nullable=False)
	img_name = db.Column(db.String(255), nullable=False)
	img_type = db.Column(db.String(10), nullable=False, default='foreign')

	def __repr__(self):
		return '<ArticleImage %r>' % self.img_id

class MainData(db.Model):
    main_data_id = db.Column(db.Integer, primary_key=True)
    data_name = db.Column(db.String(100), nullable=False)
    data_value = db.Column(db.String(100), nullable=False)
    is_link = db.Column(db.Boolean, nullable=False, default=False)
    data_link = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return '<Article %r>' % self.main_data_id   # ❌
# --------- вспомогательные функции -------
@app.context_processor
def inject_auth():
    return dict(auth=is_auth())


def is_auth():
    try:
        if session['auth'] == True:
            return True
        else:
            return False
    except:
        return False
def is_auth_else_return_main():
    if session['auth'] == True:
        pass
    else:
        return redirect('/')

def save_image(file):
	original = secure_filename(file.filename)
	ext = original.rsplit('.', 1)[1].lower()
	unique_name = f"{uuid.uuid4().hex}.{ext}"
	path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
	file.save(path)
	return unique_name
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('auth') is not True:
            return render_template('404.html'), 404
        return f(*args, **kwargs)
    return wrapper


#------обработка страниц -------
#изменение главной страницы
@app.route('/main-data-management', methods=['GET', 'POST'])
@login_required
def main_data_management():
    main_data = MainData.query.all()
    if not main_data:
            new_main_data = MainData(data_name='default', data_value='default', is_link=False, data_link="default")
            db.session.add(new_main_data)
            db.session.commit()
    if request.method == 'POST':
        for row in main_data:
            row.data_name = request.form.get(f'data_name{row.main_data_id}')
            row.data_value = request.form.get(f'data_value{row.main_data_id}')
            row.is_link = f'is_link{row.main_data_id}' in request.form
            row.data_link = request.form.get(f'data_link{row.main_data_id}')

        db.session.commit()
        return redirect('/')
    else:
        main_data = MainData.query.all()
        return render_template('main_data_management.html', main_data=main_data)


#добавление новой информации
@app.route('/add-main-data', methods=['GET', 'POST'])
@login_required
def add_main_data():
    if request.method == 'POST':
        new_data_name = request.form.get(f'data_name_new')
        new_data_value = request.form.get(f'data_value_new')
        new_is_link = f'is_link_new' in request.form
        new_data_link = request.form.get(f'data_link_new')

        new_main_data = MainData(data_name=new_data_name, data_value=new_data_value, is_link=new_is_link, data_link=new_data_link)
        db.session.add(new_main_data)
        db.session.commit()
        return redirect('/main-data-management')
    else:
        return render_template('add_main_data.html')


@app.route('/delete-main-data/<int:main_data_id>', methods=['POST'])
@login_required
def delete_main_data(main_data_id):
    main_data = MainData.query.get_or_404(main_data_id)
    db.session.delete(main_data)
    db.session.commit()
    return redirect('/main-data-management')


#главная страница
@app.route('/')
@app.route('/home')
def index():
    main_data = MainData.query.all()
    return render_template('index.html', main_data=main_data)


#создание постов
@app.route('/create-article', methods=['POST', 'GET'])
@login_required
def create_article():
    if request.method == 'POST':
        article_title = request.form['article_title']
        article_text = request.form['article_text']

        article = Article(article_title=article_title, article_text=article_text)
        db.session.add(article)
        db.session.flush()   # ← получаем article_id

        # --- главная картинка ---
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '' and allowed_file(main_file.filename):
            unique_name = save_image(main_file)
            db.session.add(ArticleImage(
                article_id=article.article_id,
                img_name=unique_name,
                img_type='primary',
            ))

        # --- дополнительные картинки ---
        for file in request.files.getlist('secondary_images'):
            if file and file.filename != '' and allowed_file(file.filename):
                unique_name = save_image(file)
                db.session.add(ArticleImage(
                    article_id=article.article_id,
                    img_name=unique_name,
                    img_type='foreign',
                ))

        db.session.commit()
        return redirect('/posts')
    else:
        return render_template('create_article.html')


#редактирование постов
@app.route('/edit-article/<int:article_id>', methods=['POST', 'GET'])
@login_required
def edit_article(article_id):
    article = Article.query.get_or_404(article_id)

    if request.method == 'POST':
        # 1. текст
        article.article_title = request.form['article_title']
        article.article_text = request.form['article_text']

        # 2. замена главной
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '' and allowed_file(main_file.filename):
            old_primary = ArticleImage.query.filter_by(
                article_id=article_id, img_type='primary'
            ).first()
            if old_primary:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_primary.img_name)
                if os.path.exists(old_path):
                    os.remove(old_path)
                db.session.delete(old_primary)

            unique_name = save_image(main_file)
            db.session.add(ArticleImage(
                article_id=article_id,
                img_name=unique_name,
                img_type='primary',
            ))

        # 3. удаление отмеченных
        for img_id in request.form.getlist('delete_images'):
            img = ArticleImage.query.get(int(img_id))
            if img and img.article_id == article_id:
                path = os.path.join(app.config['UPLOAD_FOLDER'], img.img_name)
                if os.path.exists(path):
                    os.remove(path)
                db.session.delete(img)

        # 4. добавление новых  ← ЭТОГО У ТЕБЯ НЕТ
        for file in request.files.getlist('secondary_images'):
            if file and file.filename != '' and allowed_file(file.filename):
                unique_name = save_image(file)
                db.session.add(ArticleImage(
                    article_id=article_id,
                    img_name=unique_name,
                    img_type='foreign',
                ))

        db.session.commit()
        return redirect(url_for('post_detail', article_id=article_id))

    return render_template('edit_article.html', article=article)

#удаление поста
@app.route('/delete-article/<int:article_id>', methods=['POST'])
@login_required
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)

    # удаляем файлы с диска
    for img in article.images:
        path = os.path.join(app.config['UPLOAD_FOLDER'], img.img_name)
        if os.path.exists(path):
            os.remove(path)

    # удаляем статью (картинки в БД — каскадом)
    db.session.delete(article)
    db.session.commit()

    flash('Пост удалён', 'success')
    return redirect(url_for('posts'))


#посты
@app.route('/posts')
@app.route('/posts/<int:page>')
def posts(page = 1):
	per_page = 8
	pagination = Article.query.order_by(Article.article_date.desc()).paginate(page=page, per_page=per_page, error_out = False)
	articles = pagination.items
	return render_template('posts.html', articles=articles, pagination=pagination)


#просмотр постов
@app.route('/posts/detail/<int:article_id>')
def post_detail(article_id):
	article = Article.query.get(article_id)
	return render_template('post_detail.html', article=article)


#админ вход
@app.route('/admin', methods=['POST', 'GET'])
def admin():
    if request.method == 'POST':
        if request.form['login'] == Admin.login and request.form['password'] == Admin.password:
            session['auth'] = True
            return redirect('/success_auth')
        else:
            session['auth'] = False
            return redirect('/')
    else:
        return render_template('admin.html')

# успешный вход в паннель
@app.route('/success_auth')
def test_session():
	if is_auth():
		return render_template('success_auth.html')
	else:
		return render_template('404.html'), 404


#ошибка 404
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)