from email.header import decode_header
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
import os
import poplib
import email
import datetime
import json
import time
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_script():
    while True:
        try:
            load_dotenv()
            MAIL_SERVER = os.getenv("MAIL_SERVER")
            MAIL_USERNAME = os.getenv("MAIL_USERNAME")
            MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

            with open('printer_models.json') as f:
                printer_models = json.load(f)

            prefixes = [prefix for sublist in printer_models.values() for prefix in sublist]

            mail = poplib.POP3_SSL(MAIL_SERVER)

            mail.user(MAIL_USERNAME)
            mail.pass_(MAIL_PASSWORD)

            num_messages = len(mail.list()[1])
        
            if num_messages == 0:
                logging.info("Mailbox empty, skipping the process.")
                mail.quit()
                time.sleep(900)
                continue

            saved_message_ids = set()
            if os.path.exists('temp/saved_message_ids.txt'):
                with open('temp/saved_message_ids.txt', 'r') as f:
                    saved_message_ids = set(line.strip() for line in f)

            with open('temp/saved_message_ids.txt', 'a') as id_file:
                for i in range(num_messages):
                    raw_mail = b'\n'.join(mail.retr(i+1)[1])
                    email_message = email.message_from_bytes(raw_mail)
                    message_id = email_message['Message-ID']

                    if message_id not in saved_message_ids:
                        if email_message.is_multipart():
                            logging.info(f"Email {message_id} has an attachment, skipping.")
                            continue

                        for part in email_message.walk():
                            if part.get_content_type() == "text/plain":
                                mail_text = part.get_payload(decode=True)
                                mail_text = mail_text.decode()

                                if len(mail_text) > 1000:
                                    logging.info(f"Email {message_id} is too long, skipping.")
                                    continue

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

            mail.quit()
            time.sleep(900)
        except Exception as e:
            logging.error(f"Error: {e}. Mail server might be down, it's not responding. Retrying in 5 minutes.")
            time.sleep(600)

if __name__ == '__main__':
    run_script()