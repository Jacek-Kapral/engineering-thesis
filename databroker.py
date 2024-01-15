import os
import re
import datetime
import time
from dotenv import load_dotenv
import pymysql.cursors
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.txt'):
            logging.info(f"File {event.src_path} has been modified.")
            process_file(event.src_path)

def process_file(file_path):
    db = pymysql.connect(
        host=os.getenv('MYSQL_DB_HOST'),
        user=os.getenv('MYSQL_DB_USER'),
        password=os.getenv('MYSQL_ROOT_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE'),
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = db.cursor()

    with open(file_path, 'r') as file:
        content = file.read()

        match = re.search(r'\d{4}-\d{2}-\d{2}', file_path)
        if match:
            date = datetime.datetime.strptime(match.group(), '%Y-%m-%d').date()

        match = re.search(r'\[Serial Number\],(.{0,25})', content)
        if match:
            serial_number = match.group(1).strip()

            cursor.execute("SELECT id, service_contract, tax_id FROM printers WHERE serial_number = %s", (serial_number,))
            printer = cursor.fetchone()
            if printer and printer['service_contract']: 
                match_black = re.search(r'\[Total Black Counter\],(\d{0,25})', content)
                match_color = re.search(r'\[Total Color Counter\],(\d{0,25})', content)
                match_total = re.search(r'\[Total Counter\],(\d{0,25})', content)
                if match_black or match_color or match_total:
                    if match_color:
                        counter_color = match_color.group(1).strip()
                        counter_black = match_black.group(1).strip() if match_black else None
                    else:
                        counter_color = "0"
                        counter_black = match_total.group(1).strip() if match_total else None
                    cursor.execute("INSERT INTO print_history (printers_id, date, counter_black_history, counter_color_history) VALUES (%s, %s, %s, %s)",
                                (printer['id'], date, counter_black, counter_color))
                    db.commit()

        match = re.search(r'Installed Place :(.{0,25})', content)
        if match:
            serial_number = match.group(1).strip()
            cursor.execute("SELECT id, tax_id FROM printers WHERE serial_number = %s", (serial_number,))
            printer = cursor.fetchone()
            if printer: 
                match = re.search(r'Error :(.+)', content)
                if match:
                    error = match.group(1).strip()
                    cursor.execute("SELECT id, times_happend FROM service_requests WHERE printer_id = %s AND service_request = %s AND DATE(request_date) = %s",
                                (printer['id'], error, date))
                    service_request = cursor.fetchone()

                    if service_request:  
                        cursor.execute("UPDATE service_requests SET times_happend = times_happend + 1 WHERE id = %s",
                                    (service_request['id'],))
                    else:
                        cursor.execute("INSERT INTO service_requests (printer_id, tax_id, service_request) VALUES (%s, %s, %s)",
                                    (printer['id'], printer['tax_id'], error))
                    db.commit()
    db.close()

if __name__ == "__main__":
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, path='/app/temp', recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()