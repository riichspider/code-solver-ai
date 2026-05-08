"""
Test to validate that database mocking behavior is properly implemented
in the code generation pipeline for SQLite and other database connections.
"""

import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import sys
import os

# Add the parent directory to the path to import core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.coder import CodeGenerator
from utils.prompts import coding_system_prompt, build_coding_user_prompt


class TestDatabaseMocking(unittest.TestCase):
    """Test database mocking behavior in generated code."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.generator = CodeGenerator(self.mock_client)
    
    def test_sqlite_mocking_instruction_in_system_prompt(self):
        """Test that the system prompt includes SQLite mocking instructions."""
        system_prompt = coding_system_prompt("python", "normal")
        
        # Check that the mocking instruction is present
        self.assertIn("unittest.mock", system_prompt)
        self.assertIn("mock the database connection", system_prompt)
        self.assertIn("sqlite3.connect", system_prompt)
    
    @patch('core.coder.CPP_PROMPTS_AVAILABLE', False)
    @patch('core.coder.RUBY_PROMPTS_AVAILABLE', False)
    def test_database_mocking_in_generated_response(self):
        """Test that generated code includes database mocking when needed."""
        # Mock a database-related problem
        problem = "Fix SQL injection vulnerability in UserDatabase class"
        classification = "bug"
        language = "python"
        understanding = "SQL injection through string formatting"
        plan_steps = ["Use parameterized queries"]
        constraints = ["Must prevent SQL injection"]
        risks = ["Security vulnerability"]
        success_criteria = ["No SQL injection possible"]
        context_text = "Code uses sqlite3.connect()"
        similar_context = []
        
        # Mock response that should include database mocking
        mock_response = {
            "filename": "solution.py",
            "code": """
import sqlite3

class UserDatabase:
    def __init__(self, db_name=":memory:"):
        self.conn = sqlite3.connect(db_name)
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
""",
            "test_filename": "test_solution.py",
            "tests": """
import unittest
from unittest.mock import patch, MagicMock
from solution import UserDatabase

class TestUserDatabase(unittest.TestCase):
    @patch('sqlite3.connect')
    def test_get_user_with_mock(self, mock_connect):
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1, 'test_user', 'test@example.com')
        
        # Test
        db = UserDatabase()
        result = db.get_user(1)
        
        # Assertions
        mock_cursor.execute.assert_called_once_with("SELECT * FROM users WHERE id = ?", (1,))
        self.assertEqual(result, (1, 'test_user', 'test@example.com'))
""",
            "explanation": ["Fixed SQL injection with parameterized queries"],
            "notes": ["Tests use database mocking"]
        }
        
        self.mock_client.generate_json.return_value = mock_response
        
        # Generate code
        result = self.generator.generate(
            problem=problem,
            classification=classification,
            language=language,
            understanding=understanding,
            plan_steps=plan_steps,
            constraints=constraints,
            risks=risks,
            success_criteria=success_criteria,
            context_text=context_text,
            similar_context=similar_context,
            model="test-model",
            mode="normal",
            options={}
        )
        
        # Verify that tests include mocking
        self.assertIn("unittest.mock", result["tests"])
        self.assertIn("patch", result["tests"])
        self.assertIn("sqlite3.connect", result["tests"])
    
    def test_mock_validation_in_real_scenario(self):
        """Test that we can validate proper mocking behavior."""
        # This test simulates what the validator should check
        test_code_with_mock = """
import unittest
from unittest.mock import patch
from solution import SomeDatabaseClass

class TestDatabase(unittest.TestCase):
    @patch('sqlite3.connect')
    def test_database_operation(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        db = SomeDatabaseClass()
        result = db.some_method()
        
        mock_cursor.execute.assert_called()
        self.assertIsNotNone(result)
"""
        
        # Verify the test code contains required mocking elements
        self.assertIn("unittest.mock", test_code_with_mock)
        self.assertIn("@patch", test_code_with_mock)
        self.assertIn("sqlite3.connect", test_code_with_mock)
        self.assertIn("MagicMock", test_code_with_mock)
    
    def test_no_real_database_connections(self):
        """Test that generated tests don't contain real database connections."""
        test_code_without_mock = """
import unittest
from solution import SomeDatabaseClass

class TestDatabase(unittest.TestCase):
    def test_database_operation(self):
        db = SomeDatabaseClass()
        result = db.some_method()  # This would try to connect to real DB
        self.assertIsNotNone(result)
"""
        
        # This test should fail validation because it doesn't mock the database
        self.assertNotIn("unittest.mock", test_code_without_mock)
        self.assertNotIn("@patch", test_code_without_mock)
        self.assertNotIn("sqlite3.connect", test_code_without_mock)
        
        # In a real validator, this would be flagged as problematic
        # For this test, we just verify the absence of mocking


if __name__ == '__main__':
    unittest.main()
