from flask import Flask, render_template, url_for, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from functools import wraps

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
    current_season_name = db.Column(db.String(100), nullable=False)
    current_season_link = db.Column(db.String(100), nullable=False)
    current_tg_name = db.Column(db.String(100), nullable=False)
    current_tg_link = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return '<Article %r>' % self.main_data_id
# --------- вспомогательные функции -------
@app.context_processor
def inject_auth():
    return dict(auth=is_auth())


def is_auth():
    if session['auth'] == True:
        return True
    else:
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
    main_data = MainData.query.first()
    if request.method == 'POST':
        if main_data is None:
            main_data = MainData()
            db.session.add(main_data)
        main_data.current_season_name = request.form['current_season_name']
        main_data.current_season_link = request.form['current_season_link']
        main_data.current_tg_name = request.form['current_tg_name']
        main_data.current_tg_link = request.form['current_tg_link']

        db.session.commit()
        return redirect('/')
    else:
        main_data = MainData.query.first()
        return render_template('main_data_management.html', main_data=main_data)


#главная страница
@app.route('/')
@app.route('/home')
def index():
    main_data = MainData.query.first()
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


#посты
@app.route('/posts')
@app.route('/posts/<int:page>')
def posts(page = 1):
	per_page = 3
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
        if request.form['login'] == 'Cuptyom' and request.form['password'] == '123':
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