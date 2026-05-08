import re

mongo_code = '''
from pymongo import MongoClient

def get_documents():
    client = MongoClient('mongodb://localhost:27017/')
    return client.db.collection.find()
'''

db_patterns = [
    r'sqlite3\.connect',
    r'psycopg2\.connect',
    r'mysql\.connector\.connect',
    r'pymongo\.MongoClient',
    r'from\s+pymongo\s+import',
    r'engine\s*=\s*create_engine',
    r'Database\.connect',
    r'Connection\(',
]

print(f"Mongo code: {repr(mongo_code)}")

for i, pattern in enumerate(db_patterns):
    match = re.search(pattern, mongo_code)
    print(f"Pattern {i}: {pattern} -> Match: {bool(match)}")
    if match:
        print(f"  Matched: {repr(match.group(0))}")

uses_db = any(re.search(pattern, mongo_code) for pattern in db_patterns)
print(f"\nUses DB: {uses_db}")
