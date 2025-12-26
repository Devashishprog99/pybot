"""
Database Test Script
Run this to check if the database is working correctly
"""

import sys
sys.path.insert(0, 'e:\\bots tg\\gmail-marketplace-bot')

from database import db

print("=== DATABASE TEST ===\n")

# Test 1: Check if database file exists
import os
db_path = "e:\\bots tg\\gmail-marketplace-bot\\gmail_marketplace.db"
if os.path.exists(db_path):
    print(f"✅ Database file exists: {db_path}")
    size = os.path.getsize(db_path)
    print(f"   Size: {size} bytes\n")
else:
    print(f"❌ Database file NOT found: {db_path}\n")

# Test 2: Get all users
try:
    users = db.get_all_users()
    print(f"✅ Users found: {len(users)}")
    if users:
        for user in users[:5]:
            print(f"   - User ID: {user.get('user_id')}, Username: {user.get('username', 'N/A')}")
    else:
        print("   No users in database yet")
    print()
except Exception as e:
    print(f"❌ Error getting users: {e}\n")

# Test 3: Get all sellers
try:
    sellers = db.get_pending_sellers()
    print(f"✅ Pending sellers: {len(sellers)}")
    if sellers:
        for seller in sellers[:5]:
            print(f"   - Seller ID: {seller.get('seller_id')}, User ID: {seller.get('user_id')}")
    else:
        print("   No pending sellers")
    print()
except Exception as e:
    print(f"❌ Error getting sellers: {e}\n")

# Test 4: Get stats
try:
    stats = db.get_stats()
    print(f"✅ Statistics:")
    print(f"   Total users: {stats.get('total_users', 0)}")
    print(f"   Available Gmails: {stats.get('available_gmails', 0)}")
    print(f"   Sold Gmails: {stats.get('sold_gmails', 0)}")
    print(f"   Pending sellers: {stats.get('pending_sellers', 0)}")
    print()
except Exception as e:
    print(f"❌ Error getting stats: {e}\n")

print("=== TEST COMPLETE ===")
