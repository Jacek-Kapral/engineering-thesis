import os
import re
import datetime
import time
from dotenv import load_dotenv
import pymysql.cursors
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Check if the modified file is a .txt file
        if event.src_path.endswith('.txt'):
            logging.info(f"File {event.src_path} has been modified.")
            # Call your processing function here
            process_file(event.src_path)

def process_file(file_path):
    # Connect to the MySQL database
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

        # Extract date from filename
        date = datetime.datetime.strptime(file_path[-14:-4], '%Y-%m-%d').date()

        # Check if there's a "[Serial Number]," string
        match = re.search(r'\[Serial Number\],(.+)', content)
        if match:
            serial_number = match.group(1).strip()

            # Check if the serial number is present in printers.serial_number
            cursor.execute("SELECT id, service_contract, tax_id FROM printers WHERE serial_number = %s", (serial_number,))
            printer = cursor.fetchone()
            if printer and printer[1]:  # If the printer exists and has a service contract
                # Check for the "[Total Black Counter]," and "[Total Color Counter]," strings
                match_black = re.search(r'\[Total Black Counter\],(.+)', content)
                match_color = re.search(r'\[Total Color Counter\],(.+)', content)
                match_total = re.search(r'\[Total Counter\],(.+)', content)
                if match_black or match_color or match_total:
                    counter_black = match_black.group(1).strip() if match_black else match_total.group(1).strip() if match_total else None
                    counter_color = match_color.group(1).strip() if match_color else None

                    # Insert the counters into print_history
                    cursor.execute("INSERT INTO print_history (printers_id, date, counter_black_history, counter_color_history) VALUES (%s, %s, %s, %s)",
                                   (printer[0], date, counter_black, counter_color))
                    db.commit()

        # Check if there's a "Installed Place :" string
        match = re.search(r'Installed Place :(.+)', content)
        if match:
            serial_number = match.group(1).strip()

            # Check if the serial number is present in printers.serial_number
            cursor.execute("SELECT id, tax_id FROM printers WHERE serial_number = %s", (serial_number,))
            printer = cursor.fetchone()
            if printer:  # If the printer exists
                # Check for the "Error :" string
                match = re.search(r'Error :(.+)', content)
                if match:
                    error = match.group(1).strip()

                    # Insert the error into service_requests
                    cursor.execute("INSERT INTO service_requests (printer_id, tax_id, service_request) VALUES (%s, %s, %s)",
                                   (printer[0], printer[1], error))
                    db.commit()

    # Close the database connection
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