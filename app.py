import configparser
import os
import logging
from functools import wraps
from flask import Flask, render_template, request, session, g, redirect, url_for, flash, get_flashed_messages, abort, jsonify, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from pymysql.err import IntegrityError
from datetime import datetime
from pygal.style import Style
from weasyprint import HTML
from dotenv import load_dotenv
import pymysql
import pygal
import json

with open('printer_models.json') as f:
    printer_models_from_file = json.load(f)

load_dotenv()
config = configparser.ConfigParser()
config.read('config.ini')

flask_env = config['flask']['env']
flask_app = config['flask']['app']
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['ENV'] = flask_env
app.secret_key = os.environ.get('SECRET_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

app.jinja_env.auto_reload = True


class User(UserMixin):
    def __init__(self, id, username, password_hash, admin, email):
        if not isinstance(id, int):
            raise ValueError('id must be an integer')
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
    return pymysql.connect(
        host=os.getenv('MYSQL_DB_HOST'),
        user=os.getenv('MYSQL_DB_USER'),
        password=os.getenv('MYSQL_ROOT_PASSWORD'),
        db=os.getenv('MYSQL_DATABASE'),
        cursorclass=pymysql.cursors.DictCursor
    )

def get_user_by_id(user_id):
    try:
        user_id = int(user_id)
    except ValueError:
        return None

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users WHERE id = %s"
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
    user_id = int(user_id)
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
        company_name = request.form['company_name']
        tax_id = request.form['tax_id']
        address = request.form['address']
        postal_code = request.form['postal_code']
        city = request.form['city']
        phone = request.form['phone']
        company_email = request.form['company_email']

        with connection.cursor() as cursor:
            sql = "INSERT INTO users(login, password, admin, email) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (login, password, True, email))
            sql = "INSERT INTO my_company(company_name, tax_id, address, postal_code, city, phone, email) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (company_name, tax_id, address, postal_code, city, phone, company_email))
        connection.commit()

        msg = Message('Admin account created', sender='noreply@example.com', recipients=[email])
        msg.body = f"Hello,\nYou've just registered Your admin account in Printer Fleet Manager App, \nusing given email address, with following data about Your company:\n{ tax_id }\n{ company_name }\n{ address }\n{ postal_code } { city }\n{ phone }\n{ company_email }\nHave a nice experience managing Your printer fleet!"
        mail.send(msg)

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

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form['email']
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE email = %s AND admin = 1"
            cursor.execute(sql, (email,))
            admin = cursor.fetchone()

        if admin is None:
            flash('No admin account found with the provided email.', 'danger')
            return redirect(url_for('reset_password'))

        token = s.dumps(email, salt='email-confirm')
        msg = Message('Password reset token', sender='noreply@example.com', recipients=[email])
        msg.body = 'Your password reset token is {}'.format(token)
        mail.send(msg)
        return 'Email sent!'
    return render_template('admpassreset.html')

@app.route('/confirm_reset/<token>', methods=['GET', 'POST'])
def confirm_reset(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)
    except SignatureExpired:
        return '<p>The token is expired!</p>'
    if request.method == 'POST':
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        return 'Password reset!'
    return render_template('confirmreset.html', token=token)

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
        user_id = int(user_id)
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE id = %s"
            cursor.execute(sql, (user_id,))
            g.user = cursor.fetchone()

@app.before_request
def require_login():
    allowed_routes = ['register_admin', 'login', 'static', 'home', 'logout', 'reset_password', 'confirm_reset']
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
            if not isinstance(user_data['id'], int):
                raise ValueError('user id must be an integer')
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

        assigned = 'assigned' in request.form
        company = request.form.get('company', None)

        if assigned and company:
            with connection.cursor() as cursor:
                sql = "SELECT tax_id FROM clients WHERE company = %s"
                cursor.execute(sql, (company,))
                result = cursor.fetchone()
                if result is not None:
                    tax_id = result['tax_id']
                else:
                    flash('No client with this company name found.', 'error')
                    return redirect(url_for('add_printer'))
        else:
            tax_id = None

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

        # Insert initial print history for the new printer
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO print_history (printers_id, date, counter_black_history, counter_color_history)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (printer_id, datetime.now(), counter_black, counter_color))
            connection.commit()

        flash('Printer, contract, and initial print history added.', 'success')
        return redirect(url_for('index'))
    else:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM clients"
            cursor.execute(sql)
            clients = cursor.fetchall()

        return render_template('add_printer.html', printer_models=printer_models, clients=clients)

@app.route('/printers', methods=['GET'])
@admin_required
def printers():
    page = request.args.get('page', 1, type=int)
    filter_query = request.args.get('filter', '')
    per_page = 10
    offset = (page - 1) * per_page
    try: # for debugging purposes
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            SELECT printers.id, printers.serial_number, printers.model, printers.black_counter, printers.color_counter, clients.company
            FROM printers
            LEFT JOIN clients ON printers.tax_id = clients.tax_id
            WHERE printers.serial_number LIKE %s OR printers.model LIKE %s
            ORDER BY printers.id
            LIMIT %s OFFSET %s
            """
            cursor.execute(sql, ('%' + filter_query + '%', '%' + filter_query + '%', per_page, offset))
            printers = cursor.fetchall()

        return render_template('printers.html', printers=printers, page=page)
    except Exception as e: # for debugging purposes
        print(f"An error occurred when executing the SQL query: {e}")
        return render_template('printers.html', printers=[], page=1)

@app.route('/get_printers/<string:tax_id>', methods=['GET'])
@login_required
def get_printers(tax_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM printers WHERE tax_id = %s", (tax_id,))
        printers = cursor.fetchall()
    return jsonify(printers)

@app.route('/edit_printer/<int:printer_id>', methods=['GET', 'POST'])
@admin_required
def edit_printer(printer_id):
    connection = get_db_connection()
    if request.method == 'POST':
        printer_serial_number = request.form['serial_number']
        model = request.form['model']
        assigned = 'assigned' in request.form
        active = 'active' in request.form
        contract_id = request.form['contract_id']

        if assigned:
            tax_id = request.form['company']
        else:
            tax_id = None  

        with connection.cursor() as cursor:
            sql = "SELECT black_counter, color_counter FROM printers WHERE id=%s"
            cursor.execute(sql, (printer_id,))
            counter_data = cursor.fetchone()
            if counter_data is not None:
                counter_black = counter_data['black_counter']
                counter_color = counter_data['color_counter']
                print("Counter Black:", counter_black)
                print("Counter Color:", counter_color)
            else:
                print("No data found for printer with ID:", printer_id)

            sql = """
            UPDATE printers SET serial_number=%s, model=%s, assigned=%s, active=%s, contract_id=%s, 
            black_counter=%s, color_counter=%s, tax_id=%s
            WHERE id=%s
            """
            cursor.execute(sql, (printer_serial_number, model, assigned, active, contract_id, counter_black, 
                                 counter_color, tax_id, printer_id))
            connection.commit()

        return redirect(url_for('printers'))

    else:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM printers WHERE id=%s"
            cursor.execute(sql, (printer_id,))
            printer = cursor.fetchone()
            if printer is not None:
                printer = dict(printer)

            sql = "SELECT * FROM clients"
            cursor.execute(sql)
            clients = cursor.fetchall()

        return render_template('edit_printer.html', printer=printer, clients=clients)

@app.route('/delete_printer/<int:printer_id>', methods=['POST'])
def delete_printer(printer_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "DELETE FROM print_history WHERE printers_id = %s"
        cursor.execute(sql, (printer_id,))
        
        sql = "DELETE FROM service_requests WHERE printer_id = %s"
        cursor.execute(sql, (printer_id,))
        
        sql = "DELETE FROM printers WHERE id = %s"
        cursor.execute(sql, (printer_id,))
        
    connection.commit()
    flash('Printer, associated service requests, and print history deleted successfully.', 'success')
    return redirect(url_for('index'))

    
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
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO clients(tax_id, company, city, postal_code, address, phone, email) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (tax_id, company, city, postal_code, address, phone, email))
            connection.commit()
            flash('Client registered.', 'success')
        except IntegrityError:
            flash('Client with this tax id is already in the database.', 'error')
            return redirect(url_for('register_client'))

        return redirect(url_for('index'))
    return render_template('registerclient.html')

@app.route('/clients', methods=['GET'])
@login_required
def clients():
    page = request.args.get('page', 1, type=int)
    filter_query = request.args.get('filter', '')
    per_page = 10
    offset = (page - 1) * per_page
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM clients WHERE tax_id LIKE %s OR company LIKE %s ORDER BY tax_id LIMIT %s OFFSET %s"
        cursor.execute(sql, ('%' + filter_query + '%', '%' + filter_query + '%', per_page, offset))
        clients = cursor.fetchall()
    return render_template('clients.html', clients=clients, page=page)

@app.route('/edit_client/<string:tax_id>', methods=['GET', 'POST'])
@admin_required
def edit_client(tax_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM clients WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))
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
            cursor.execute(sql, (tax_id, company, city, postal_code, address, phone, email, client['id']))
        connection.commit()

        flash('Client details updated successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('edit_client.html', client=client)

@app.route('/client_printers/<int:tax_id>')
def client_printers(tax_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT company FROM clients WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))
        result = cursor.fetchone()
        if result is not None:
            client_name = result['company']
        else:
            client_name = "Unknown"
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.*
        FROM printers
        INNER JOIN clients ON printers.tax_id = clients.tax_id
        WHERE clients.tax_id = %s
        """
        cursor.execute(sql, (tax_id,))
        printers = cursor.fetchall()

    if not printers:
        flash('No printers assigned to this client.', 'info')

    return render_template('client_printers.html', printers=printers, client_name=client_name)

@app.route('/search_clients', methods=['POST'])
@login_required
def search_clients():
    search_string = request.form.get('search_string')
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM clients WHERE company LIKE %s OR tax_id LIKE %s", (search_string+'%', search_string+'%'))
        clients = cursor.fetchall()
    return render_template('search_results.html', clients=clients)

@app.route('/printer/<int:printer_id>')
@login_required
def printer_info(printer_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.*, clients.company 
        FROM printers 
        LEFT JOIN clients ON printers.tax_id = clients.tax_id 
        WHERE printers.id = %s
        """
        cursor.execute(sql, (printer_id,))
        printer = cursor.fetchone()

        sql = """
        SELECT * FROM service_requests 
        WHERE printer_id = %s
        """
        cursor.execute(sql, (printer_id,))
        service_requests = cursor.fetchall()

        sql = """
        SELECT * FROM print_history 
        WHERE printers_id = %s
        """
        cursor.execute(sql, (printer_id,))
        rows = cursor.fetchall()

        print_history = []
        for i in range(len(rows)):
            row = rows[i]
            if i > 0 and printer['contract_id'] is not None and printer['price_black'] is not None and printer['price_color'] is not None:
                prev_row = rows[i - 1]
                black_diff = row['counter_black_history'] - prev_row['counter_black_history']
                color_diff = row['counter_color_history'] - prev_row['counter_color_history']
                black_cost = black_diff * printer['price_black']
                color_cost = color_diff * printer['price_color']
                row['black_cost'] = black_cost
                row['color_cost'] = color_cost
            print_history.append(row)

        custom_style = Style(
            font_family='Segoe UI',
            colors=('#545454', '#80bdff'),
        )
        line_chart = pygal.Line(style=custom_style, height=400, width=600, legend_at_bottom=True, show_legend=True)
        line_chart.title = 'Print History (X-axis: Date, Y-axis: Count)'

        dates = [history['date'] for history in print_history]
        black_counters = [history['counter_black_history'] for history in print_history]
        color_counters = [history['counter_color_history'] for history in print_history]
        line_chart.x_labels = dates
        line_chart.add('Black Counter', black_counters)
        line_chart.add('Color Counter', color_counters)

        graph_svg = line_chart.render()

        graph_svg = graph_svg.decode('utf-8')

        return render_template('printer_info.html', printer=printer, service_requests=service_requests, print_history=print_history, graph_svg=graph_svg)

@app.route('/users')
@admin_required
def users():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM users"
        cursor.execute(sql)
        users = cursor.fetchall()
    return render_template('users.html', users=users)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    connection = get_db_connection()
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        admin = request.form['admin'] == 'true'
        email = request.form['email']
        update_user_in_db(user_id, login, password, admin, email)
        flash('User details updated.', 'success')
        return redirect(url_for('edit_user', user_id=user_id))
    else:
        user = get_user_by_id(user_id)
        return render_template('edit_user.html', user=user)

@app.route('/get_printers/', methods=['GET'])
@login_required
def get_all_printers():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM printers")
        printers = cursor.fetchall()
    return jsonify(printers)

@app.route('/service_requests', methods=['GET'])
@admin_required
def service_requests():
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    total_requests = None
    service_requests = None
    users = None
    try:
        offset = (page - 1) * per_page
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            SELECT service_requests.*, printers.serial_number, printers.model, clients.company
            FROM service_requests
            JOIN printers ON service_requests.printer_id = printers.id
            JOIN clients ON printers.tax_id = clients.tax_id
            WHERE service_requests.active = TRUE
            ORDER BY service_requests.request_date DESC
            LIMIT %s OFFSET %s
            """
            cursor.execute(sql, (per_page, offset))
            raw_service_requests = cursor.fetchall()

            if all(isinstance(row, dict) for row in raw_service_requests):
                service_requests = {row['id']: row for row in raw_service_requests}

            cursor.execute("SELECT * FROM users")
            raw_users = cursor.fetchall()

            if all(isinstance(row, dict) for row in raw_users):
                users = {row['id']: row for row in raw_users}

            cursor.execute("SELECT COUNT(*) as count FROM service_requests WHERE active = TRUE")
            result = cursor.fetchone()
            total_requests = result['count'] if result is not None else 0

        return render_template('service_requests.html', service_requests=service_requests, users=users)
    except Exception as e:
        return render_template('service_requests.html', page=page, per_page=per_page, total_requests=total_requests, service_requests=service_requests, users=users) 

@app.route('/new_service_request', methods=['GET'])
@login_required
def new_service_request():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM clients")
        clients = cursor.fetchall()
        cursor.execute("SELECT * FROM printers")
        printers = cursor.fetchall()
    return render_template('new_service_request.html', clients=clients, printers=printers)

@app.route('/submit_service_request', methods=['POST'])
@login_required
def submit_service_request():
    service_request = request.form.get('service_request')
    printer_id = request.form.get('printer_id')
    tax_id = request.form.get('tax_id')

    # Check if service_request and tax_id are strings
    if not isinstance(service_request, str) or not isinstance(tax_id, str):
        flash('Invalid service request or company tax ID', 'error')
        return redirect(url_for('service_requests'))

    try:
        # Check if printer_id is an integer
        printer_id = int(printer_id)
    except ValueError:
        flash('Invalid printer ID', 'error')
        return redirect(url_for('service_requests'))

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        INSERT INTO service_requests (service_request, printer_id, tax_id)
        VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (service_request, printer_id, tax_id))
        connection.commit()

    return redirect(url_for('service_requests'))

@app.route('/view_printers/<string:tax_id>', methods=['GET'])
@login_required
def view_printers(tax_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM printers WHERE tax_id = %s", (tax_id,))
        printers = cursor.fetchall()
    return render_template('client_printers.html', printers=printers) 

@app.route('/new_service_request_for_printer/<string:printer_serial_number>', methods=['GET'])
@login_required
def new_service_request_for_printer(printer_serial_number):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM printers WHERE serial_number = %s", (printer_serial_number,))
        printer = cursor.fetchone()

        cursor.execute("SELECT * FROM clients WHERE tax_id = %s", (printer['tax_id'],))
        clients = cursor.fetchone()

    return render_template('new_service_request_for_printer.html', printer=printer, clients=clients)

@app.route('/service_requests', methods=['POST'])
@login_required
def create_service_request():
    tax_id = request.form.get('company')
    printer_id = request.form.get('printer_id')
    service_request = request.form.get('service_request')

    if not isinstance(tax_id, str):
        flash('Invalid company tax ID', 'error')
        return redirect(url_for('new_service_request'))

    try:
        printer_id = int(printer_id)
        service_request = str(service_request)
    except ValueError:
        flash('Invalid printer ID or service request ID', 'error')
        return redirect(url_for('new_service_request'))

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM clients WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))
        client = cursor.fetchone()

        if client is None:
            flash('The company does not exist.', 'error')
            return redirect(url_for('new_service_request'))

        sql = "SELECT * FROM printers WHERE id = %s"
        cursor.execute(sql, (printer_id,))
        printer = cursor.fetchone()

        if printer is None:
            flash('The printer does not exist.', 'error')
            return redirect(url_for('new_service_request'))

        sql = "INSERT INTO service_requests (service_request, printer_id, company) VALUES (%s, %s, %s)"
        cursor.execute(sql, (service_request, printer_id, tax_id)) 
        connection.commit()

    return redirect(url_for('service_requests'))


@app.route('/assign_user', methods=['POST'])
@admin_required
def assign_user():
    user_id = request.form.get('user_id')
    request_id = request.form.get('request_id')

    if not user_id or not request_id:
        flash('Missing user_id or request_id', 'error')
        return redirect(url_for('service_requests'))

    try:
        user_id = int(user_id)
        request_id = int(request_id)
    except ValueError:
        flash('Invalid user_id or request_id', 'error')
        return redirect(url_for('service_requests'))

    connection = get_db_connection()

    with connection.cursor() as cursor:
        sql = "UPDATE service_requests SET assigned_to = %s WHERE id = %s"
        cursor.execute(sql, (user_id, request_id))
        connection.commit()

    return redirect(url_for('service_requests'))

@app.route('/my_requests', methods=['GET'])
@login_required
def my_requests():
    if not isinstance(current_user.id, int):
        abort(400, description="User id must be an integer")

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT service_requests.*, clients.company, printers.serial_number, printers.model 
        FROM service_requests 
        JOIN clients ON service_requests.tax_id = clients.tax_id 
        JOIN printers ON service_requests.printer_id = printers.id
        WHERE service_requests.assigned_to = %s AND service_requests.active = TRUE
        """
        cursor.execute(sql, (current_user.id,))
        service_requests = cursor.fetchall()

    return render_template('my_requests.html', service_requests=service_requests)

@app.route('/mark_done', methods=['POST'])
@login_required
def mark_done():
    request_id = request.form.get('request_id')
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "UPDATE service_requests SET active = FALSE WHERE id = %s"
        cursor.execute(sql, (request_id,))
        connection.commit()

    user = get_user_by_id(current_user.get_id())

    if user['admin'] == 1:
        return redirect(url_for('service_requests'))
    else:
        return redirect(url_for('my_requests'))

@app.route('/delete_request/<int:id>', methods=['POST'])
@admin_required
def delete_request(id):
    app.logger.info(f"id: {id}") # for debugging purposes
    try: # for debugging purposes
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "DELETE FROM service_requests WHERE id = %s"
            cursor.execute(sql, (id,))
            connection.commit()
        return redirect(url_for('service_requests'))
    except Exception as e: # for debugging purposes
        print(f"An error occurred when executing the SQL query: {e}")
        return redirect(url_for('service_requests'))

@app.route('/archived_requests', methods=['GET'])
def archived_requests():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    client_name = request.args.get('client_name', None)
    tax_id = request.args.get('tax_id', None)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT COUNT(*) FROM service_requests WHERE active = 0"

            cursor.execute(sql)
            result = cursor.fetchone()
            # app.logger.info(f"Type of result: {type(result)}, value of result: {result}") # for debugging purposes
            if result is not None:
                total_requests = result['COUNT(*)']
            else:
                total_requests = 0
            sql = """
            SELECT 
                service_requests.service_request,
                service_requests.request_date,
                users.login AS assigned_to,
                clients.company AS client_name,
                printers.serial_number AS printer_serial_number
            FROM service_requests
            INNER JOIN users ON service_requests.assigned_to = users.id
            INNER JOIN clients ON service_requests.tax_id = clients.tax_id
            INNER JOIN printers ON service_requests.printer_id = printers.id
            WHERE service_requests.active = 0
            """

            if client_name:
                sql += " AND clients.company = %s"
            if tax_id:
                sql += " AND clients.tax_id = %s"

            sql += " LIMIT %s OFFSET %s"

            cursor.execute(sql, (client_name, tax_id, per_page, (page - 1) * per_page) if client_name and tax_id else (client_name or tax_id, per_page, (page - 1) * per_page) if client_name or tax_id else (per_page, (page - 1) * per_page))

            archived_requests = cursor.fetchall()
            app.logger.info(archived_requests)
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        archived_requests = []
        total_requests = 0

    return render_template('archived_requests.html', archived_requests=archived_requests, page=page, per_page=per_page, total_requests=total_requests)

@app.route('/delete_client/<string:tax_id>', methods=['POST'])
@login_required
def delete_client(tax_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "DELETE FROM service_requests WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))

        sql = "UPDATE printers SET tax_id = NULL WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))

        sql = "DELETE FROM clients WHERE tax_id = %s"
        cursor.execute(sql, (tax_id,))

    connection.commit()

    return redirect(url_for('index'))

@app.route('/print_history', methods=['GET'])
def print_history():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM print_history"
        cursor.execute(sql)
        history = cursor.fetchall()

    return render_template('print_history.html', history=history)

@app.route('/generate_pdf/<int:request_id>', methods=['GET', 'POST'])
@login_required
def generate_pdf(request_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql_company = """
        SELECT company_name, tax_id, address, postal_code, city, email, phone
        FROM my_company
        WHERE id = 1
        """
        cursor.execute(sql_company)
        company = cursor.fetchone()

        sql_request = """
        SELECT 
            clients.company, clients.address, clients.postal_code, clients.city, clients.tax_id, clients.phone, clients.email,
            printers.serial_number, printers.model, printers.additional_info,
            (SELECT counter_black_history FROM print_history WHERE printers_id = printers.id ORDER BY date DESC LIMIT 1) as black_print_history,
            (SELECT counter_color_history FROM print_history WHERE printers_id = printers.id ORDER BY date DESC LIMIT 1) as color_print_history,
            service_requests.request_date, service_requests.service_request,
            users.login
        FROM 
            service_requests
        INNER JOIN 
            clients ON service_requests.tax_id = clients.tax_id
        INNER JOIN 
            printers ON service_requests.printer_id = printers.id
        INNER JOIN 
            users ON service_requests.assigned_to = users.id
        WHERE 
            service_requests.id = %s
        """
        cursor.execute(sql_request, (request_id,))
        request = cursor.fetchone()

        html = render_template('report.html', company=company, request=request)

        pdf = HTML(string=html).write_pdf()

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=output.pdf'

        return response

@app.route('/knowledge_base')
def knowledge_base():
    with open('printer_models.json') as f:
        printer_models = json.load(f)
    return render_template('knowledge_base.html', printer_models=printer_models)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)