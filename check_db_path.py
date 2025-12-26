"""
Quick diagnostic to check database path being used
"""
import os
from database import db
import config

print("=" * 50)
print("DATABASE DIAGNOSTIC")
print("=" * 50)
print(f"DATABASE_PATH from config: {config.DATABASE_PATH}")
print(f"Database instance path: {db.db_path}")
print(f"Absolute path: {os.path.abspath(db.db_path)}")
print(f"File exists: {os.path.exists(db.db_path)}")
if os.path.exists(db.db_path):
    size = os.path.getsize(db.db_path)
    print(f"File size: {size} bytes")
print("=" * 50)

# Check if we can read from it
try:
    stats = db.get_stats()
    print(f"Users in DB: {stats['total_users']}")
    print(f"Sellers in DB: {stats.get('pending_sellers', 0)}")
    print("Database is accessible!")
except Exception as e:
    print(f"ERROR accessing database: {e}")
print("=" * 50)
