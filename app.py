import configparser
from flask import Flask, render_template, request
from werkzeug.security import generate_password_hash
import pymysql.cursors

config = configparser.ConfigParser()
config.read('config.ini')

flask_env = config['flask']['env']
flask_app = config['flask']['app']

app = Flask(__name__)
app.config['ENV'] = flask_env

def get_db_connection():
    config = configparser.ConfigParser()
    config.read('config.ini')

    return pymysql.connect(host=config['database']['host'],
                           user=config['database']['user'],
                           password=config['database']['password'],
                           database=config['database']['database'],
                           cursorclass=pymysql.cursors.DictCursor)

@app.route('/')
def index():
    return render_template('index.html')

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
    return render_template('add_printer.html')

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
        name = request.form['name']

        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO users(login, password, admin, email, name) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (login, password, admin, email, name))
        connection.commit()

        return 'User registered.' 

    return render_template('register.html')

@app.route('/register_client', methods=['GET', 'POST'])
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

    return render_template('register_client.html')

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