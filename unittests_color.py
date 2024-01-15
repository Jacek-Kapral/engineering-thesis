import unittest
from unittest.mock import patch, MagicMock
import datetime
from databroker import process_file

class TestProcessFile(unittest.TestCase):
    @patch('pymysql.connect')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="""
    [Model Name],Envilab
    [Serial Number], A4FM021007478
    [Send Date],01/06/23
    [Total Counter],00400999
    [Total Color Counter],00175268
    [Total Black Counter],00225731
    [Total Scan/Fax Counter],00058674
    [Operating Accumulation Time], 0.0, 5.9, 6.0, 14.4, 9.3, 11.7, 8.8,
    9.6, 8.9, 8.9, 8.5, 8.3
    [Energizing Accumulation Time],
    0.9,429.5,271.4,501.7,320.2,615.1,508.3,412.3,401.8,316.3,309.6,457.1
    [Standing Accumulation Time], 0.0, 46.4, 61.3,131.1, 86.6, 92.1, 66.6,
    89.6, 79.8,104.7,101.4, 98.1
    [Power Saving Accumulation Time],
    0.9,377.2,204.1,356.2,224.3,511.2,432.9,313.1,313.0,202.8,199.6,350.7
    """)
    def test_process_file(self, mock_open, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        # Mock the file path
        file_path = "temp/2023-06-22-19-54-27-A4FM021007478.txt"

        # Mock the printer data
        printer_data = {"id": 1, "service_contract": True, "tax_id": "1234412444"}

        # Mock the fetchone() method to return the printer data
        mock_cursor.fetchone.return_value = printer_data

        # Call the function
        process_file(file_path)

        # Check if the correct SQL queries were executed
        mock_cursor.execute.assert_any_call("SELECT id, service_contract, tax_id FROM printers WHERE serial_number = %s", ("A4FM021007478",))
        mock_cursor.execute.assert_any_call("INSERT INTO print_history (printers_id, date, counter_black_history, counter_color_history) VALUES (%s, %s, %s, %s)",
                                                    (1, datetime.date(2023, 6, 22), "00225731", "00175268"))

        # Check if the database connection was closed
        mock_db.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()