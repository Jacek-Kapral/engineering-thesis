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
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "INSERT INTO printers(serial_number) VALUES (%s)"
            cursor.execute(sql, (printer_serial_number,))
        connection.commit()
        return 'Printer serial number ' + printer_serial_number + ' saved.'
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)