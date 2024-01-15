import unittest
from unittest.mock import patch, MagicMock
import datetime
from databroker import process_file

class TestProcessFile(unittest.TestCase):
    @patch('pymysql.connect')
    def test_process_file(self, mock_connect):
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        file_content = """
        [Model Name],EngiLab
        [Serial Number], A1UG021109838
        [Send Date],03/10/23
        [Total Counter],00185186
        [Total Scan/Fax Counter],00041513
        """

        file_path = "temp/2023-10-03-19-58-16-A1UG021109838.txt"
        printer_data = {"id": 1, "service_contract": True, "tax_id": "1234412444"}
        mock_cursor.fetchone.return_value = printer_data

        process_file(file_path)

        mock_cursor.execute.assert_any_call("SELECT id, service_contract, tax_id FROM printers WHERE serial_number = %s", ("A1UG021109838",))
        mock_cursor.execute.assert_any_call("INSERT INTO print_history (printers_id, date, counter_black_history, counter_color_history) VALUES (%s, %s, %s, %s)",
                                                    (1, datetime.date(2023, 10, 3), "00185186", "0"))

        mock_db.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()