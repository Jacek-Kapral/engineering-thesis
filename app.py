import configparser
import os
from flask import Flask, render_template, request, session, g, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

config = configparser.ConfigParser()
config.read('config.ini')

flask_env = config['flask']['env']
flask_app = config['flask']['app']

app = Flask(__name__)
app.config['ENV'] = flask_env
app.secret_key = os.environ.get('SECRET_KEY')

printer_models = {
    "A4FM": "Bizhub C224",
    "AA2M": "Bizhub C250i",
    "A7R0": "Bizhub C258",
    ""
    # Add more models here
}

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
        return redirect(url_for('login'))

@app.before_request
def require_login():
    allowed_routes = ['login', 'register_admin']
    if 'user_id' not in session and request.endpoint not in allowed_routes and request.method != 'GET':
        return redirect(url_for('login'))

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE login = %s"
            cursor.execute(sql, (login,))
            user = cursor.fetchone()

        if user is None or not check_password_hash(user['password'], password):
            return 'Invalid login or password.'

        session['user_id'] = user['id']
        return redirect(url_for('index'))

    return render_template('login.html', show_menu=False)

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_printer', methods=['GET', 'POST'])
def add_printer():
    if request.method == 'POST':
        printer_serial_number = request.form['printer_serial_number']
        counter_black = int(request.form['counter_black'])
        counter_color = int(request.form['counter_color'])
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO printers(serial_number, black_counter, color_counter) VALUES (%s, %s, %s)"
            cursor.execute(sql, (printer_serial_number, counter_black, counter_color))
        connection.commit()
        return 'Printer data saved.'
    return render_template('add_printer.html', printer_models=printer_models)

@app.route('/printers', methods=['GET'])
def printers():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT printers.id, printers.serial_number, printers.black_counter, printers.color_counter, clients.company, contracts.id as contract_id
        FROM printers
        LEFT JOIN clients ON printers.tax_id = clients.tax_id
        LEFT JOIN contracts ON printers.id = contracts.printer_id
        """
        cursor.execute(sql)
        printers = cursor.fetchall()

    return render_template('printers.html', printers=printers)

@app.route('/register', methods=['GET', 'POST'])
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

        return 'User registered.' 

    return render_template('register.html')

@app.route('/registerclient', methods=['GET', 'POST'])
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

        return 'Client registered.' 

    return render_template('registerclient.html')

@app.route('/add_contract', methods=['GET', 'POST'])
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

        return 'Contract added.'  # or redirect the user after successful addition

    else:
        with connection.cursor() as cursor:
            sql = "SELECT tax_id, company FROM clients"
            cursor.execute(sql)
            clients = cursor.fetchall()

            sql = "SELECT id, serial_number FROM printers"
            cursor.execute(sql)
            printers = cursor.fetchall()

        return render_template('add_contract.html', clients=clients, printers=printers)

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