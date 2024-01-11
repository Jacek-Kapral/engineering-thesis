import os
import imaplib
import email
import datetime
import json
import time
import threading
from email.header import decode_header
from dotenv import load_dotenv
import re
from email.utils import parsedate_to_datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_script():
    while True:
        load_dotenv()
        MAIL_SERVER = os.getenv("MAIL_SERVER")
        MAIL_USERNAME = os.getenv("MAIL_USERNAME")
        MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

        with open('printer_models.json') as f:
            printer_models = json.load(f)

        prefixes = [prefix for sublist in printer_models.values() for prefix in sublist]

        mail = imaplib.IMAP4_SSL(MAIL_SERVER)

        mail.login(MAIL_USERNAME, MAIL_PASSWORD)

        mail.select('inbox')

        result, data = mail.uid('search', None, "ALL") 
        email_ids = data[0].split()
        num_messages = len(email_ids)

         if num_messages == 0:
            logging.info("Mailbox empty, skipping the process.")
            mail.logout()
            time.sleep(900)
            continue

        saved_message_ids = set()
        if os.path.exists('temp/saved_message_ids.txt'):
            with open('temp/saved_message_ids.txt', 'r') as f:
                saved_message_ids = set(line.strip() for line in f)

        with open('temp/saved_message_ids.txt', 'a') as id_file:
            for i in email_ids:
                result, data = mail.uid('fetch', i, '(BODY.PEEK[])') 
                raw_mail = data[0][1]
                email_message = email.message_from_bytes(raw_mail)
                message_id = email_message['Message-ID']

                if message_id not in saved_message_ids:
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            mail_text = part.get_payload(decode=True)
                            mail_text = mail_text.decode()

                            date_sent = email_message['Date']
                            date_sent = parsedate_to_datetime(date_sent)
                            date_sent_str = date_sent.strftime('%Y-%m-%d-%H-%M-%S')

                            serial_number_match = re.search(r'\[Serial Number\], (.*)', mail_text)
                            installed_place_match = re.search(r'Installed Place :(.*)', mail_text)
                            if serial_number_match:
                                identifier = serial_number_match.group(1).strip()
                            elif installed_place_match:
                                identifier = installed_place_match.group(1).strip()
                            else:
                                identifier = 'unknown'

                            with open(f'temp/{date_sent_str}-{identifier}.txt', 'w') as f:
                                f.write(mail_text)

                    id_file.write(message_id + ' __ ' + date_sent_str + '\n')
                    saved_message_ids.add(message_id)

        mail.logout()
        time.sleep(900)

if __name__ == '__main__':
    thread = threading.Thread(target=run_script)
    thread.start()