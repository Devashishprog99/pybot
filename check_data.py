import sqlite3
from database import db

# Check users
conn = sqlite3.connect('gmail_marketplace.db')
conn.row_factory = sqlite3.Row
users = conn.execute('SELECT * FROM users').fetchall()
print(f'Total users: {len(users)}')
for u in users:
    print(f'- User ID: {u["user_id"]}, Username: {u["username"]}, Role: {u["role"]}')

# Check pending payments
print('\n=== Sellers Awaiting Payment ===')
payments = db.get_sellers_awaiting_payment()
print(f'Total: {len(payments)}')
for p in payments:
    print(f'- Seller: {p.get("username")}, Sold: {p.get("sold_count")}, Amount: {p.get("amount_owed")}')

# Check sold gmails
print('\n=== Sold Gmails (unpaid) ===')
sold_gmails = conn.execute("SELECT * FROM gmails WHERE status = 'sold' AND paid_to_seller = 0").fetchall()
print(f'Total unpaid sold gmails: {len(sold_gmails)}')

conn.close()
