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

@app.route('/printers')
def printers():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM printers"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)