from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
db = SQLAlchemy(app)


class Article(db.Model):
	article_id = db.Column(db.Integer, primary_key=True)
	article_title = db.Column(db.String(100), nullable=False)
	article_text = db.Column(db.Text, nullable=False)
	article_date = db.Column(db.DateTime, default=datetime.utcnow)

	def __repr__(self):
		return '<Article %r>' % self.id

#главная страница
@app.route('/')
@app.route('/home')
def index():
	return render_template('index.html')

#посты
@app.route('/posts')
def posts():
	articles = Article.query.order_by(Article.article_date.desc()).all()
	return render_template('posts.html', articles=articles)


#создание постов
@app.route('/create-article', methods=['POST', 'GET'])
def create_article():
	if request.method == 'POST':
		article_title = request.form['article_title']
		article_text = request.form['article_text']

		article = Article(article_title=article_title, article_text=article_text)

		try:
			db.session.add(article)
			db.session.commit()
			return redirect('/posts')
		except:
			return "произошла ошибка"
	else:
		return render_template('create_article.html')


#просмотр постов
@app.route('/posts/<int:article_id>')
def post_detail(article_id):
	article = Article.query.get(article_id)
	return render_template('post_detail.html', article=article)


#ошибка 404
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)