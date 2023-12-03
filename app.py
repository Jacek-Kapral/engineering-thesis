import configparser
import os
from functools import wraps
from flask import Flask, render_template, request, session, g, redirect, url_for, flash, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import json
import logging

with open('printer_models.json') as f:
    printer_models_from_file = json.load(f)

config = configparser.ConfigParser()
config.read('config.ini')

flask_env = config['flask']['env']
flask_app = config['flask']['app']

app = Flask(__name__)
app.config['ENV'] = flask_env
app.secret_key = os.environ.get('SECRET_KEY')

class User(UserMixin):
    def __init__(self, id, username, password_hash, admin, email):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.admin = admin
        self.email = email

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

printer_models = {}
for model, prefixes in printer_models_from_file.items():
    for prefix in prefixes:
        printer_models[prefix] = model

def get_db_connection():
    config = configparser.ConfigParser()
    config.read('config.ini')

    return pymysql.connect(host=config['database']['host'],
                           user=config['database']['user'],
                           password=config['database']['password'],
                           database=config['database']['database'],
                           cursorclass=pymysql.cursors.DictCursor)

@app.route('/', methods=['GET'])
def home():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users WHERE admin = 1"
        cursor.execute(sql)
        admin = cursor.fetchone()

    if admin is None:
        return redirect(url_for('register_admin'))
    else:
        return redirect(url_for('login', show_menu=False))

@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users WHERE id = %s"
        cursor.execute(sql, (user_id,))
        user_data = cursor.fetchone()
    if user_data:
        return User(user_data['id'], user_data['login'], user_data['password'], user_data['admin'], user_data['email'])
    else:
        return None

@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users WHERE admin = 1"
        cursor.execute(sql)
        admin = cursor.fetchone()

    if admin is not None:
        return redirect(url_for('login'))

    if request.method == 'POST':
        login = request.form['login']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']

        with connection.cursor() as cursor:
            sql = "INSERT INTO users(login, password, admin, email) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (login, password, True, email))
        connection.commit()

        return redirect(url_for('login'))

    return render_template('register_admin.html', show_menu=False)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.admin:
            flash('You do not have access to this page.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/index', methods=['GET'])
def index():
    return render_template('index.html')

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE id = %s"
            cursor.execute(sql, (user_id,))
            g.user = cursor.fetchone()

@app.before_request
def require_login():
    print("Checking if login is required")
    allowed_routes = ['register_admin', 'login', 'static', 'home', 'logout']
    if not current_user.is_authenticated and request.endpoint not in allowed_routes:
        print("Redirecting to login")
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if '_flashes' in session:
        session['_flashes'] = [msg for msg in get_flashed_messages() if msg != 'Logged out.']
    if request.method == 'POST':
        username = request.form['login']
        password = request.form['password']
        connection = get_db_connection()

        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE login = %s"
            cursor.execute(sql, (username,))
            user_data = cursor.fetchone()

        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['login'], user_data['password'], user_data['admin'], user_data['email'])

            login_user(user)

            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
            return render_template('login.html', show_menu=False)
    else:
        return render_template('login.html', show_menu=False)

@app.route('/logout')
@login_required
def logout():
    logging.warning("Logging out user") # For debugging purposes
    logout_user()
    flash('Logged out.')
    session.clear()  # Clear the session
    return redirect(url_for('login', _external=True))

@app.route('/add_printer', methods=['GET', 'POST'])
@admin_required
def add_printer():
    if request.method == 'POST':
        printer_serial_number = request.form['printer_serial_number']
        counter_black = request.form['counter_black']
        counter_color = request.form['counter_color']
        counter_black = int(counter_black) if counter_black else 0
        counter_color = int(counter_color) if counter_color else 0
        prefix = printer_serial_number[:4] if len(printer_serial_number) >= 4 else printer_serial_number
        if prefix not in printer_models:
            prefix = printer_serial_number[:6] if len(printer_serial_number) >= 6 else printer_serial_number
        printer_model = printer_models.get(prefix)
        if not printer_model:
            printer_model = request.form['model'] 
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO printers(serial_number, black_counter, color_counter, model) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (printer_serial_number, counter_black, counter_color, printer_model))
        connection.commit()
        flash('Printer added.', 'success')
        return redirect(url_for('index'))
    return render_template('add_printer.html', printer_models=printer_models)

@app.route('/printers', methods=['GET'])
def printers():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.id, printers.serial_number, printers.model, printers.black_counter, printers.color_counter, clients.company, contracts.id as contract_id
        FROM printers
        LEFT JOIN clients ON printers.tax_id = clients.tax_id
        LEFT JOIN contracts ON printers.id = contracts.printer_id
        """
        cursor.execute(sql)
        printers = cursor.fetchall()

    return render_template('printers.html', printers=printers)

@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    if request.method == 'POST':
        login = request.form['login']
        password = generate_password_hash(request.form['password'])
        admin = 'admin' in request.form
        email = request.form['email']
        
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO users(login, password, admin, email) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (login, password, admin, email))
        connection.commit()

        flash('User registered.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/registerclient', methods=['GET', 'POST'])
@admin_required
def register_client():
    if request.method == 'POST':
        tax_id = request.form['tax_id']
        company = request.form['company']
        city = request.form['city']
        postal_code = request.form['postal_code']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']

        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO clients(tax_id, company, city, postal_code, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (tax_id, company, city, postal_code, address, phone, email))
        connection.commit()

        flash('Client registered.', 'success')
        return redirect(url_for('index'))
    return render_template('registerclient.html')

@app.route('/add_contract', methods=['GET', 'POST'])
@admin_required
def add_contract():
    connection = get_db_connection()
    if request.method == 'POST':
        price_black = request.form['price_black']
        price_color = request.form['price_color']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        tax_id = request.form['tax_id']
        printer_id = request.form['printer_id']

        with connection.cursor() as cursor:
            sql = "INSERT INTO contracts(price_black, price_color, start_date, end_date, tax_id) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (price_black, price_color, start_date, end_date, tax_id))
        connection.commit()

        flash('Contract added.', 'success')
        return redirect(url_for('index'))

    else:
        with connection.cursor() as cursor:
            sql = "SELECT tax_id, company FROM clients"
            cursor.execute(sql)
            clients = cursor.fetchall()

            sql = "SELECT id, serial_number FROM printers"
            cursor.execute(sql)
            printers = cursor.fetchall()

        return render_template('add_contract.html', clients=clients, printers=printers)

@app.route('/users')
def users():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users"
        cursor.execute(sql)
        users = cursor.fetchall()
    return render_template('users.html', users=users)

@app.route('/print_history', methods=['GET'])
def print_history():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM print_history"
        cursor.execute(sql)
        history = cursor.fetchall()

    return render_template('print_history.html', history=history)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)