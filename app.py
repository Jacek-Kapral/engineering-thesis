from flask import Flask, render_template, request
import pymysql.cursors

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(host='db',
                           user='root',
                           password='my-secret-pw',
                           database='mydb',
                           cursorclass=pymysql.cursors.DictCursor)

@app.route('/', methods=['GET', 'POST'])
def index():
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
    return render_template('index.html')

@app.route('/printers')
def printers():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM printers"
        cursor.execute(sql)
        printers = cursor.fetchall()
    return render_template('printers.html', printers=printers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)