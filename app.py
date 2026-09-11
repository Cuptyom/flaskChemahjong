from flask import Flask, render_template, url_for

app = Flask(__name__)

@app.route('/')
@app.route('/home')
def index():
	return render_template('index.html')


@app.route('/user/<string:user_name>/<int:user_id>')
def user(user_name, user_id):
	return f"Hello {user_name}, your id is {user_id}"


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
	app.run(debug=True)