"""
Bug: SQL Injection vulnerability
Description: Python code vulnerable to SQL injection through string formatting
Expected vulnerability: Malicious input can alter SQL queries to access unauthorized data
"""

import sqlite3

class UserDatabase:
    def __init__(self, db_name=":memory:"):
        self.conn = sqlite3.connect(db_name)
        self.setup_database()
    
    def setup_database(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Insert sample data
        users = [
            (1, 'admin', 'admin@example.com', 'admin123'),
            (2, 'user1', 'user1@example.com', 'password1'),
            (3, 'user2', 'user2@example.com', 'password2')
        ]
        cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?)', users)
        self.conn.commit()
    
    def get_user_by_username(self, username):
        """
        BUG: SQL injection vulnerability through string formatting
        Should use parameterized queries instead
        """
        cursor = self.conn.cursor()
        
        # VULNERABLE: Direct string formatting allows SQL injection
        query = f"SELECT * FROM users WHERE username = '{username}'"
        print(f"Executing query: {query}")
        
        cursor.execute(query)
        return cursor.fetchone()
    
    def login(self, username, password):
        """
        BUG: SQL injection in login function
        """
        cursor = self.conn.cursor()
        
        # VULNERABLE: String formatting in WHERE clause
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        print(f"Login query: {query}")
        
        cursor.execute(query)
        user = cursor.fetchone()
        
        if user:
            return True, f"Welcome {user[1]}!"
        return False, "Invalid credentials"

def main():
    db = UserDatabase()
    
    print("=== Testing SQL Injection Vulnerabilities ===\n")
    
    # Normal usage
    print("1. Normal login attempts:")
    normal_tests = [
        ('admin', 'admin123'),
        ('user1', 'password1'),
        ('user2', 'wrongpass')
    ]
    
    for username, password in normal_tests:
        success, message = db.login(username, password)
        print(f"   Login ({username}, {password}): {message}")
    
    print("\n2. SQL Injection attacks:")
    
    # SQL injection attempts
    injection_tests = [
        ("admin' --", "anything"),  # Comment out password check
        ("' OR '1'='1", "' OR '1'='1"),  # Always true condition
        ("admin'; DROP TABLE users; --", "anything"),  # Drop table attack
        ("' OR 1=1 UNION SELECT * FROM users --", "anything"),  # Union attack
    ]
    
    for username, password in injection_tests:
        print(f"\n   Testing injection: username='{username}', password='{password}'")
        try:
            success, message = db.login(username, password)
            print(f"   Result: {message}")
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n3. Direct user lookup with injection:")
    injection_usernames = [
        "admin",
        "' OR '1'='1",
        "admin'; SELECT * FROM users --"
    ]
    
    for username in injection_usernames:
        print(f"\n   Looking up: '{username}'")
        try:
            user = db.get_user_by_username(username)
            print(f"   Result: {user}")
        except Exception as e:
            print(f"   Error: {e}")
    
    db.conn.close()

if __name__ == "__main__":
    main()

# TODO: enviar para o pipeline com: python main.py "SQL injection vulnerability in UserDatabase class - need parameterized queries"
