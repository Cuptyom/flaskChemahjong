# admin.example.py — шаблон. Скопируй в admin.py и заполни своими данными.
# Сгенерируй значения командой:
#   python -c "from werkzeug.security import generate_password_hash; import secrets; print('login =', repr(secrets.token_hex(16))); print('password_hash =', repr(generate_password_hash('ТвойПароль!'))); print('session_token =', repr(secrets.token_hex(32)))"

class Admin:
    login = 'your_login'
    password_hash = 'your_password_hash'
    session_token = 'your_secret_key_here'
    admin_pannel_url = 'your_admin_pannel_url'
    IS_PRODUCTION = False