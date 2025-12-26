#!/usr/bin/env python3
"""
Quick diagnostic script to check bot status
Run this locally to verify everything works
"""

print("=" * 50)
print("GMAIL MARKETPLACE BOT - DIAGNOSTIC CHECK")
print("=" * 50)

# Test 1: Database Connection
print("\n[1/5] Testing Database Connection...")
try:
    from database import db
    print("  ✓ Database module loaded")
except Exception as e:
    print(f"  ✗ Database import failed: {e}")
    exit(1)

# Test 2: Check Database File
print("\n[2/5] Checking Database File...")
import os
db_path = "gmail_marketplace.db"
if os.path.exists(db_path):
    size = os.path.getsize(db_path)
    print(f"  ✓ Database exists: {db_path} ({size} bytes)")
else:
    print(f"  ✗ Database not found: {db_path}")

# Test 3: Fetch Users
print("\n[3/5] Fetching Users...")
try:
    users = db.get_all_users()
    print(f"  ✓ Found {len(users)} user(s)")
    for user in users:
        print(f"    - User ID: {user['user_id']}, Username: @{user.get('username', 'N/A')}")
except Exception as e:
    print(f"  ✗ Error fetching users: {e}")

# Test 4: Fetch Sellers
print("\n[4/5] Fetching Sellers...")
try:
    sellers = db.get_pending_sellers()
    print(f"  ✓ Found {len(sellers)} pending seller(s)")
except Exception as e:
    print(f"  ✗ Error fetching sellers: {e}")

# Test 5: Get Statistics
print("\n[5/5] Getting Statistics...")
try:
    stats = db.get_stats()
    print(f"  ✓ Statistics retrieved successfully")
    print(f"    Total Users: {stats.get('total_users', 0)}")
    print(f"    Available Gmails: {stats.get('available_gmails', 0)}")
    print(f"    Pending Sellers: {stats.get('pending_sellers', 0)}")
except Exception as e:
    print(f"  ✗ Error getting stats: {e}")

# Test 6: Admin Module
print("\n[6/6] Testing Admin Module...")
try:
    from admin import AdminHandler
    import config
    admin_count = len(config.ADMIN_IDS)
    print(f"  ✓ Admin module loaded")
    print(f"    Configured admins: {admin_count}")
    print(f"    Admin IDs: {config.ADMIN_IDS}")
except Exception as e:
    print(f"  ✗ Error loading admin module: {e}")

print("\n" + "=" * 50)
print("DIAGNOSTIC COMPLETE")
print("=" * 50)
print("\nIf all tests passed above, the bot should work fine.")
print("If you still cannot see data in Telegram:")
print("  1. Restart the bot on Railway")
print("  2. Wait 30-60 seconds")
print("  3. Try /start in Telegram")
print("  4. Click Admin Panel")
print("\nIf web dashboard doesn't show data:")
print("  1. Restart the dashboard service on Railway")
print("  2. Clear browser cache")
print("  3. Login again")
