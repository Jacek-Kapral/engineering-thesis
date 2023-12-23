import configparser
import os
from functools import wraps
from flask import Flask, render_template, request, session, g, redirect, url_for, flash, get_flashed_messages, abort
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

def get_user_by_id(user_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users WHERE tax_id = %s"
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
    return user

def update_user_in_db(user_id, login, password, admin, email):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        UPDATE users
        SET login = %s, password = %s, admin = %s, email = %s
        WHERE id = %s
        """
        cursor.execute(sql, (login, password, admin, email, user_id))
    connection.commit()

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
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM service_requests ORDER BY request_date DESC LIMIT 10"
        cursor.execute(sql)
        recent_requests = cursor.fetchall()
    for request in recent_requests:
        request['request_date'] = request['request_date'].date()
    return render_template('index.html', recent_requests=recent_requests)

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
    session.clear() 
    return redirect(url_for('login', _external=True))

@app.route('/add_printer', methods=['GET', 'POST'])
@admin_required
def add_printer():
    connection = get_db_connection()
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

        price_black = request.form.get('price_black', None)  
        price_color = request.form.get('price_color', None)  
        start_date = request.form.get('start_date') or None
        tax_id = request.form.get('tax_id', None)

        with connection.cursor() as cursor:
            sql = "SELECT tax_id FROM printers WHERE serial_number = %s"
            cursor.execute(sql, (printer_serial_number,))
            result = cursor.fetchone()

        if result is not None and result['tax_id'] is not None:
            flash('This printer is already assigned to a client.', 'error')
            return redirect(url_for('add_printer'))

        with connection.cursor() as cursor:
            sql = """
            INSERT INTO printers(serial_number, black_counter, color_counter, model, price_black, price_color, contract_start_date, tax_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (printer_serial_number, counter_black, counter_color, printer_model, price_black, price_color, start_date, tax_id))
            printer_id = cursor.lastrowid
            connection.commit()

        flash('Printer and contract added.', 'success')
        return redirect(url_for('index'))
    else:
        with connection.cursor() as cursor:
            sql = "SELECT company FROM clients"
            cursor.execute(sql)
            clients = cursor.fetchall()

        return render_template('add_printer.html', printer_models=printer_models, clients=clients)

@app.route('/printers', methods=['GET'])
def printers():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            SELECT printers.id, printers.serial_number, printers.model, printers.black_counter, printers.color_counter, clients.company
            FROM printers
            LEFT JOIN clients ON printers.tax_id = clients.tax_id
            """
            cursor.execute(sql)
            printers = cursor.fetchall()
            print(printers)

        return render_template('printers.html', printers=printers)
    except Exception as e:
        print(f"An error occurred when executing the SQL query: {e}")
        return render_template('printers.html', printers=[])

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

@app.route('/clients', methods=['GET'])
@login_required
def clients():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM clients"
        cursor.execute(sql)
        clients = cursor.fetchall()
    return render_template('clients.html', clients=clients)

@app.route('/edit_client/<string:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM clients WHERE id = %s"
        cursor.execute(sql, (client_id,))
        client = cursor.fetchone()

    if client is None:
        flash('No client found with this ID.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        tax_id = request.form['tax_id']
        company = request.form['company']
        city = request.form['city']
        postal_code = request.form['postal_code']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']

        with connection.cursor() as cursor:
            sql = """
            UPDATE clients
            SET tax_id = %s, company = %s, city = %s, postal_code = %s, address = %s, phone = %s, email = %s
            WHERE id = %s
            """
            cursor.execute(sql, (tax_id, company, city, postal_code, address, phone, email, client_id))
        connection.commit()

        flash('Client details updated successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('edit_client.html', client=client)

@app.route('/client_printers/<string:client_id>', methods=['GET'])
@login_required
def client_printers(client_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.*
        FROM printers
        INNER JOIN clients ON printers.tax_id = clients.tax_id
        WHERE clients.tax_id = %s
        """
        cursor.execute(sql, (client_id,))
        printers = cursor.fetchall()

    if not printers:
        flash('No printers assigned to this client.', 'info')

    return render_template('client_printers.html', printers=printers)

@app.route('/printer/<int:printer_id>')
@login_required
def printer_info(printer_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.*, clients.company 
        FROM printers 
        LEFT JOIN contracts ON printers.id = contracts.printer_id 
        LEFT JOIN clients ON contracts.tax_id = clients.tax_id 
        WHERE printers.id = %s
        """
        cursor.execute(sql, (printer_id,))
        printer = cursor.fetchone()
    return render_template('printer_info.html', printer=printer)

@app.route('/users')
def users():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users"
        cursor.execute(sql)
        users = cursor.fetchall()
    return render_template('users.html', users=users)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    connection = get_db_connection()
    if request.method == 'POST':
        # Get the updated user details from the request form
        login = request.form['login']
        password = request.form['password']
        admin = request.form['admin'] == 'true'
        email = request.form['email']
        # Update the user details in the database
        update_user_in_db(user_id, login, password, admin, email)
        flash('User details updated.', 'success')
        return redirect(url_for('edit_user', user_id=user_id))
    else:
        # Fetch user details from the database
        user = get_user_by_id(user_id)
        return render_template('edit_user.html', user=user)

@app.route('/service_requests', methods=['GET'])
@login_required
def service_request():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM service_requests"
        cursor.execute(sql)
        service_requests = cursor.fetchall()

    return render_template('service_requests.html', service_requests=service_requests)

@app.route('/service_requests/new', methods=['GET'])
@login_required
def new_service_request():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT tax_id, company FROM clients")
        clients = cursor.fetchall()
        cursor.execute("SELECT id, serial_number FROM printers")
        printers = cursor.fetchall()

    return render_template('new_service_request.html', clients=clients, printers=printers)

@app.route('/service_requests', methods=['POST'])
@login_required
def create_service_request():
    company = request.form.get('company')
    printer_id = request.form.get('printer_id')
    service_request = request.form.get('service_request')

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "INSERT INTO service_requests (company, printer_id, service_request) VALUES (%s, %s, %s)"
        cursor.execute(sql, (company, printer_id, service_request))
        connection.commit()

    return redirect(url_for('service_request'))

@app.route('/my-requests')
@login_required
def my_requests():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM service_requests WHERE assigned_to = %s"
        cursor.execute(sql, (current_user.id,))
        service_requests = cursor.fetchall()
    return render_template('my_requests.html', service_requests=service_requests)

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