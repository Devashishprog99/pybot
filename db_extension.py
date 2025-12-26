"""
Helper function to get seller by seller_id (for admin module)
This is an extension to database.py
"""
# Add this method to the Database class in database.py

def get_seller_by_id(self, seller_id: int) -> Optional[Dict]:
    """Get seller by seller ID"""
    conn = self.get_connection()
    try:
        row = conn.execute('''
            SELECT s.*, u.username, u.full_name
            FROM sellers s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.seller_id = ?
        ''', (seller_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
