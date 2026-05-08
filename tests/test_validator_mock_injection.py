"""
Test to validate automatic database mock injection in the validator.
"""

from core.validator import SolutionValidator
import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestValidatorMockInjection(unittest.TestCase):
    """Test automatic database mock injection in validator."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the executor to avoid real subprocess calls
        with patch('core.validator.SandboxExecutor'):
            self.validator = SolutionValidator(timeout_seconds=1)

    def test_no_injection_for_non_database_code(self):
        """Test that non-database code is not modified."""
        code = """
def add(a, b):
    return a + b
"""
        tests = """
import unittest
from solution import add

class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
"""

        modified_code, modified_tests = self.validator._inject_database_mocking(
            code, tests)

        # Should be unchanged
        self.assertEqual(modified_code, code)
        self.assertEqual(modified_tests, tests)

    def test_injection_for_sqlite_code(self):
        """Test that SQLite code gets mocking injected."""
        code = """
import sqlite3

class UserDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('users.db')
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
"""
        tests = """
import unittest
from solution import UserDatabase

class TestUserDatabase(unittest.TestCase):
    def test_get_user(self):
        db = UserDatabase()
        result = db.get_user(1)
        self.assertIsNotNone(result)
"""

        modified_code, modified_tests = self.validator._inject_database_mocking(
            code, tests)

        # Code should be unchanged
        self.assertEqual(modified_code, code)

        # Tests should be modified
        self.assertIn('import unittest.mock', modified_tests)
        self.assertIn(
            'from unittest.mock import patch, MagicMock', modified_tests)
        self.assertIn('def setup_database_mock():', modified_tests)
        self.assertIn(
            '@patch("sqlite3.connect", side_effect=mock_sqlite_connect)', modified_tests)

    def test_no_double_injection(self):
        """Test that already mocked tests don't get double injection."""
        code = """
import sqlite3

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('test.db')
"""
        tests = """
import unittest
from unittest.mock import patch
from solution import Database

class TestDatabase(unittest.TestCase):
    @patch("sqlite3.connect")
    def test_database_init(self, mock_connect):
        db = Database()
        mock_connect.assert_called_once()
"""

        modified_code, modified_tests = self.validator._inject_database_mocking(
            code, tests)

        # Should not add additional mocking
        self.assertEqual(modified_code, code)
        # Tests should remain the same (no double injection)
        self.assertEqual(modified_tests, tests)

    def test_multiple_database_patterns(self):
        """Test injection for various database patterns."""
        # Test PostgreSQL
        pg_code = """
import psycopg2

def get_users():
    conn = psycopg2.connect("dbname=test user=postgres")
    return conn.execute("SELECT * FROM users").fetchall()
"""
        # Test MySQL
        mysql_code = """
import mysql.connector

def get_data():
    conn = mysql.connector.connect(host='localhost', user='root')
    return conn.cursor().execute("SELECT * FROM table").fetchall()
"""
        # Test MongoDB
        mongo_code = """
from pymongo import MongoClient

def get_documents():
    client = MongoClient('mongodb://localhost:27017/')
    return client.db.collection.find()
"""

        tests = """
import unittest
from solution import get_users

class TestDatabase(unittest.TestCase):
    def test_get_users(self):
        result = get_users()
        self.assertIsInstance(result, list)
"""

        for db_code in [pg_code, mysql_code, mongo_code]:
            # Use fresh copy of tests for each iteration
            fresh_tests = """
import unittest
from solution import get_users

class TestDatabase(unittest.TestCase):
    def test_get_users(self):
        result = get_users()
        self.assertIsInstance(result, list)
"""
            modified_code, modified_tests = self.validator._inject_database_mocking(
                db_code, fresh_tests)

            # Code should be unchanged
            self.assertEqual(modified_code, db_code)

            # Tests should be modified
            self.assertIn('import unittest.mock', modified_tests)
            self.assertIn('def setup_database_mock():', modified_tests)

    def test_mock_setup_function_content(self):
        """Test that mock setup function has correct content."""
        code = """
import sqlite3

def test_db():
    conn = sqlite3.connect('test.db')
    return conn
"""
        tests = """
import unittest
from solution import test_db

class TestDB(unittest.TestCase):
    def test_db_connection(self):
        result = test_db()
        self.assertIsNotNone(result)
"""

        _, modified_tests = self.validator._inject_database_mocking(
            code, tests)

        # Check mock setup function content
        self.assertIn('mock_conn = MagicMock()', modified_tests)
        self.assertIn('mock_cursor = MagicMock()', modified_tests)
        self.assertIn(
            'mock_cursor.fetchone.return_value = (1, \'test_user\', \'test@example.com\', \'password123\')', modified_tests)
        self.assertIn(
            'mock_cursor.fetchall.return_value = [(1, \'test_user\', \'test@example.com\', \'password123\')]', modified_tests)
        self.assertIn('mock_cursor.rowcount = 1', modified_tests)

    def test_patch_decorator_placement(self):
        """Test that @patch decorators are correctly placed."""
        code = """
import sqlite3

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('test.db')
    
    def query(self, sql):
        return self.conn.execute(sql).fetchall()
"""
        tests = """
import unittest
from solution import Database

class TestDatabase(unittest.TestCase):
    def test_database_query(self):
        db = Database()
        result = db.query("SELECT * FROM users")
        self.assertIsInstance(result, list)
    
    def test_other_method(self):
        pass
"""

        _, modified_tests = self.validator._inject_database_mocking(
            code, tests)

        # Check that patch decorator is added before database-related test
        lines = modified_tests.split('\n')
        test_db_line = None
        test_other_line = None

        for i, line in enumerate(lines):
            if 'def test_database_query(' in line:
                test_db_line = i
            elif 'def test_other_method(' in line:
                test_other_line = i

        # The database test should have @patch decorator
        self.assertIsNotNone(test_db_line)
        self.assertIn(
            '@patch("sqlite3.connect", side_effect=mock_sqlite_connect)', lines[test_db_line - 1])

        # The non-database test might not have the decorator
        # (depending on keyword detection)

    @patch('core.validator.SandboxExecutor')
    def test_end_to_end_validation_with_mocking(self, mock_executor):
        """Test that the full validation process works with mock injection."""
        # Mock the executor result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test passed"
        mock_result.stderr = ""
        mock_result.timed_out = False
        mock_result.duration_seconds = 0.1

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_result
        mock_executor.return_value = mock_executor_instance

        # Create validator with mocked executor
        validator = SolutionValidator(timeout_seconds=1)

        code = """
import sqlite3

def get_user_count():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER)")
    cursor.execute("INSERT INTO users VALUES (1)")
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]
"""
        tests = """
import unittest
from solution import get_user_count

class TestUserCount(unittest.TestCase):
    def test_get_user_count(self):
        count = get_user_count()
        self.assertEqual(count, 1)
"""

        # Test validation with mocked executor
        result = validator.validate(
            language="python",
            code=code,
            tests=tests,
            filename="solution.py",
            test_filename="test_solution.py"
        )

        # Should pass with mocked executor
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['returncode'], 0)

        # Verify executor was called (meaning validation ran)
        mock_executor_instance.run.assert_called()


if __name__ == '__main__':
    unittest.main()
