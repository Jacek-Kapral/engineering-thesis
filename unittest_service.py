import unittest
from unittest.mock import patch, MagicMock
import datetime
from databroker import process_file

class TestProcessFile(unittest.TestCase):
    @patch('pymysql.connect')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="""
    Occurred Time :02/12/2023 01:46:21
    Installed Place :A1UG021109838
    IP Address :192.168.1.245
    Error : Misfeed detected. 66-33
    """)
    def test_process_file_service_request(self, mock_open, mock_connect):
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        file_path = "temp/2023-12-02-01-46-31-A1UG021109838.txt"


        printer_data = {"id": 1, "tax_id": "1234412444"}


        mock_cursor.fetchone.side_effect = [printer_data, None]


        process_file(file_path)


        mock_cursor.execute.assert_any_call("SELECT id, tax_id FROM printers WHERE serial_number = %s", ("A1UG021109838",))
        mock_cursor.execute.assert_any_call("SELECT id, times_happend FROM service_requests WHERE printer_id = %s AND service_request = %s AND DATE(request_date) = %s",
                                                    (1, "Misfeed detected. 66-33", datetime.date(2023, 12, 2)))
        mock_cursor.execute.assert_any_call("INSERT INTO service_requests (printer_id, tax_id, service_request) VALUES (%s, %s, %s)",
                                                    (1, "1234412444", "Misfeed detected. 66-33"))


        mock_db.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()