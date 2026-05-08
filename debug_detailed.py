from core.validator import SolutionValidator
import sys
sys.path.append('.')

validator = SolutionValidator()

# Test PostgreSQL case
pg_code = '''
import psycopg2

def get_users():
    conn = psycopg2.connect("dbname=test user=postgres")
    return conn.execute("SELECT * FROM users").fetchall()
'''

fresh_tests = '''
import unittest
from solution import get_users

class TestDatabase(unittest.TestCase):
    def test_get_users(self):
        result = get_users()
        self.assertIsInstance(result, list)
'''

print("=== Input ===")
print(f"Code: {repr(pg_code)}")
print(f"Tests: {repr(fresh_tests)}")

modified_code, modified_tests = validator._inject_database_mocking(
    pg_code, fresh_tests)

print("\n=== Output ===")
print(f"Modified Code: {repr(modified_code)}")
print(f"Modified Tests: {repr(modified_tests)}")

print(f"\nHas unittest.mock: {'import unittest.mock' in modified_tests}")
print(
    f"Has setup_database_mock: {'def setup_database_mock():' in modified_tests}")
print(f"Has @patch: {'@patch(' in modified_tests}")
