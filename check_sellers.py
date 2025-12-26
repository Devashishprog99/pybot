import sqlite3
from database import db

# Check raw database
conn = sqlite3.connect('gmail_marketplace.db')
conn.row_factory = sqlite3.Row
sellers = conn.execute('SELECT * FROM sellers ORDER BY created_at').fetchall()

print('=== ALL SELLERS IN DATABASE ===')
print(f'Total sellers: {len(sellers)}')
for s in sellers:
    print(f'\nSeller ID: {s["seller_id"]}')
    print(f'  User ID: {s["user_id"]}')
    print(f'  Status: {s["status"]}')
    print(f'  UPI QR: {s["upi_qr_path"]}')
    print(f'  Created: {s["created_at"]}')
    print(f'  Approved: {s["approved_at"]}')
conn.close()

# Check what get_all_sellers_with_stats returns
print('\n=== get_all_sellers_with_stats() ===')
sellers_stats = db.get_all_sellers_with_stats()
print(f'Returns {len(sellers_stats)} sellers')
for s in sellers_stats:
    print(f'\nSeller: {s.get("username")} (ID: {s.get("seller_id")})')
    print(f'  Status: {s.get("status")}')
    print(f'  Pending: {s.get("pending_gmails")}')
    print(f'  Available: {s.get("available_gmails")}')
    print(f'  Sold: {s.get("sold_gmails")}')
