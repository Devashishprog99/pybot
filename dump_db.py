import sqlite3

conn = sqlite3.connect('gmail_marketplace.db')
conn.row_factory = sqlite3.Row

print('=' * 50)
print('DATABASE FULL DUMP')
print('=' * 50)

# Users
users = conn.execute('SELECT * FROM users').fetchall()
print(f'\nUSERS ({len(users)}):')
for u in users:
    print(f'  - ID: {u["user_id"]}, Username: @{u["username"]}, Role: {u["role"]}')

# Sellers
sellers = conn.execute('SELECT * FROM sellers').fetchall()
print(f'\nSELLERS ({len(sellers)}):')
for s in sellers:
    print(f'  - ID: {s["seller_id"]}, User: {s["user_id"]}, Status: {s["status"]}, Created: {s["created_at"]}')

# Gmails by status
for status in ['pending', 'available', 'sold']:
    gmails = conn.execute('SELECT * FROM gmails WHERE status = ?', (status,)).fetchall()
    print(f'\nGMAILS - {status.upper()} ({len(gmails)}):')
    for g in gmails[:5]:  # Show first 5 only
        print(f'  - {g["email"]} (Seller: {g["seller_id"]}, Batch: {g["batch_id"]})')
    if len(gmails) > 5:
        print(f'  ... and {len(gmails) - 5} more')

# Summary
total_gmails = conn.execute('SELECT COUNT(*) FROM gmails').fetchone()[0]
print(f'\n{"=" * 50}')
print(f'SUMMARY:')
print(f'  Total Users: {len(users)}')
print(f'  Total Sellers: {len(sellers)}')
print(f'  Total Gmails: {total_gmails}')
print('=' * 50)

conn.close()
