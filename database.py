"""
Database operations for Gmail Marketplace Bot
"""
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import config

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database with schema"""
        conn = self.get_connection()
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, user_id: int, username: str, full_name: str) -> bool:
        """Create or update user"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name
            ''', (user_id, username, full_name))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False
        finally:
            conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.get_connection()
        try:
            row = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        conn = self.get_connection()
        try:
            rows = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def update_wallet(self, user_id: int, amount: float) -> bool:
        """Update user wallet balance"""
        conn = self.get_connection()
        try:
            conn.execute('''
                UPDATE users 
                SET wallet_balance = wallet_balance + ?
                WHERE user_id = ?
            ''', (amount, user_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating wallet: {e}")
            return False
        finally:
            conn.close()
    
    def get_wallet_balance(self, user_id: int) -> float:
        """Get user wallet balance"""
        conn = self.get_connection()
        try:
            row = conn.execute('SELECT wallet_balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
            return row['wallet_balance'] if row else 0.0
        finally:
            conn.close()
    
    def ban_user(self, user_id: int, banned: bool = True) -> bool:
        """Ban or unban user"""
        conn = self.get_connection()
        try:
            conn.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (banned, user_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    # ==================== SELLER OPERATIONS ====================
    
    def create_seller(self, user_id: int, upi_qr_path: str) -> bool:
        """Register user as seller"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT INTO sellers (user_id, upi_qr_path, status)
                VALUES (?, ?, 'pending')
            ''', (user_id, upi_qr_path))
            conn.commit()
            
            # Update user role
            conn.execute("UPDATE users SET role = 'seller' WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating seller: {e}")
            return False
        finally:
            conn.close()
    
    def get_seller(self, user_id: int) -> Optional[Dict]:
        """Get seller by user ID"""
        conn = self.get_connection()
        try:
            row = conn.execute('SELECT * FROM sellers WHERE user_id = ?', (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
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
    
    def approve_seller(self, seller_id: int, admin_id: int, approved: bool = True) -> bool:
        """Approve or reject seller"""
        conn = self.get_connection()
        try:
            status = 'approved' if approved else 'rejected'
            conn.execute('''
                UPDATE sellers 
                SET status = ?, approved_at = ?, approved_by = ?
                WHERE seller_id = ?
            ''', (status, datetime.now(), admin_id, seller_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_pending_sellers(self) -> List[Dict]:
        """Get all pending sellers"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT s.*, u.username, u.full_name
                FROM sellers s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'pending'
                ORDER BY s.created_at ASC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def update_seller_earnings(self, seller_id: int, amount: float) -> bool:
        """Update seller earnings"""
        conn = self.get_connection()
        try:
            conn.execute('''
                UPDATE sellers 
                SET total_earnings = total_earnings + ?
                WHERE seller_id = ?
            ''', (amount, seller_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    # ==================== GMAIL OPERATIONS ====================
    
    def add_gmails(self, seller_id: int, gmails: List[Tuple[str, str]], batch_id: str) -> bool:
        """Add Gmail accounts for sale"""
        conn = self.get_connection()
        try:
            for email, password in gmails:
                conn.execute('''
                    INSERT INTO gmails (seller_id, email, password, batch_id, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (seller_id, email, password, batch_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding Gmails: {e}")
            return False
        finally:
            conn.close()
    
    def approve_gmail_batch(self, batch_id: str, approved: bool = True) -> bool:
        """Approve or reject Gmail batch"""
        conn = self.get_connection()
        try:
            status = 'available' if approved else 'rejected'
            conn.execute('''
                UPDATE gmails 
                SET status = ?, approved_at = ?
                WHERE batch_id = ? AND status = 'pending'
            ''', (status, datetime.now(), batch_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_available_gmails_count(self) -> int:
        """Get count of available Gmails"""
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) as count FROM gmails WHERE status = 'available'").fetchone()
            return row['count'] if row else 0
        finally:
            conn.close()
    
    def purchase_gmails(self, buyer_id: int, quantity: int) -> List[Dict]:
        """Purchase Gmail accounts"""
        conn = self.get_connection()
        try:
            # Get available Gmails
            rows = conn.execute('''
                SELECT * FROM gmails 
                WHERE status = 'available'
                LIMIT ?
            ''', (quantity,)).fetchall()
            
            if len(rows) < quantity:
                return []
            
            gmails = [dict(row) for row in rows]
            
            # Mark as sold
            gmail_ids = [g['gmail_id'] for g in gmails]
            placeholders = ','.join('?' * len(gmail_ids))
            conn.execute(f'''
                UPDATE gmails 
                SET status = 'sold', buyer_id = ?, sold_at = ?
                WHERE gmail_id IN ({placeholders})
            ''', [buyer_id, datetime.now()] + gmail_ids)
            
            conn.commit()
            return gmails
        except Exception as e:
            print(f"Error purchasing Gmails: {e}")
            conn.rollback()
            return []
        finally:
            conn.close()
    
    def get_pending_gmail_batches(self) -> List[Dict]:
        """Get pending Gmail batches"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT g.batch_id, g.seller_id, s.user_id, u.username, 
                       COUNT(*) as count, MIN(g.created_at) as created_at,
                       GROUP_CONCAT(g.email, ', ') as sample_emails
                FROM gmails g
                JOIN sellers s ON g.seller_id = s.seller_id
                JOIN users u ON s.user_id = u.user_id
                WHERE g.status = 'pending'
                GROUP BY g.batch_id
                ORDER BY created_at ASC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_user_purchases(self, user_id: int) -> List[Dict]:
        """Get user's purchased Gmails"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM gmails 
                WHERE buyer_id = ? AND status = 'sold'
                ORDER BY sold_at DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_seller_sales(self, seller_id: int) -> Dict:
        """Get seller's sales statistics"""
        conn = self.get_connection()
        try:
            row = conn.execute('''
                SELECT 
                    COUNT(CASE WHEN status = 'sold' THEN 1 END) as sold_count,
                    COUNT(CASE WHEN status = 'available' THEN 1 END) as available_count,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count
                FROM gmails
                WHERE seller_id = ?
            ''', (seller_id,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()
    
    # ==================== TRANSACTION OPERATIONS ====================
    
    def create_transaction(self, user_id: int, txn_type: str, amount: float, 
                          cashfree_order_id: str = None, payment_link: str = None,
                          description: str = None) -> int:
        """Create transaction record"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                INSERT INTO transactions 
                (user_id, type, amount, cashfree_order_id, payment_link, description, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ''', (user_id, txn_type, amount, cashfree_order_id, payment_link, description))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def update_transaction_status(self, txn_id: int, status: str) -> bool:
        """Update transaction status"""
        conn = self.get_connection()
        try:
            conn.execute('''
                UPDATE transactions 
                SET status = ?, completed_at = ?
                WHERE txn_id = ?
            ''', (status, datetime.now(), txn_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_transaction_by_order_id(self, order_id: str) -> Optional[Dict]:
        """Get transaction by Cashfree order ID"""
        conn = self.get_connection()
        try:
            row = conn.execute('''
                SELECT * FROM transactions 
                WHERE cashfree_order_id = ?
            ''', (order_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user transaction history"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM transactions 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # ==================== WITHDRAWAL OPERATIONS ====================
    
    def create_withdrawal(self, seller_id: int, user_id: int, amount: float, upi_qr_path: str) -> int:
        """Create withdrawal request"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                INSERT INTO withdrawals 
                (seller_id, user_id, amount, upi_qr_path, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (seller_id, user_id, amount, upi_qr_path))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    
    def get_all_sellers_with_stats(self) -> List[Dict]:
        """Get all sellers with their Gmail statistics"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT 
                    s.seller_id,
                    s.user_id,
                    s.status,
                    s.total_earnings,
                    u.username,
                    u.full_name,
                    COUNT(CASE WHEN g.status = 'pending' THEN 1 END) as pending_gmails,
                    COUNT(CASE WHEN g.status = 'available' THEN 1 END) as available_gmails,
                    COUNT(CASE WHEN g.status = 'sold' THEN 1 END) as sold_gmails
                FROM sellers s
                JOIN users u ON s.user_id = u.user_id
                LEFT JOIN gmails g ON s.seller_id = g.seller_id
                GROUP BY s.seller_id
                ORDER BY s.status ASC, s.created_at DESC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_users_with_stats(self) -> List[Dict]:
        """Get all users with their purchase and selling statistics (SQLite)"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT 
                    u.*,
                    (SELECT COUNT(*) FROM gmails WHERE buyer_id = u.user_id) as total_bought,
                    (SELECT COUNT(*) FROM gmails g JOIN sellers s ON g.seller_id = s.seller_id WHERE s.user_id = u.user_id) as total_provided,
                    (SELECT COUNT(*) FROM gmails g JOIN sellers s ON g.seller_id = s.seller_id WHERE s.user_id = u.user_id AND g.status = 'sold') as total_sold
                FROM users u
                ORDER BY u.created_at DESC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_user_detail(self, user_id: int) -> Optional[Dict]:
        """Get comprehensive user detail including all activities (SQLite)"""
        conn = self.get_connection()
        try:
            user = self.get_user(user_id)
            if not user: return None
            
            seller = self.get_seller(user_id)
            
            purchases = [dict(r) for r in conn.execute('SELECT * FROM gmails WHERE buyer_id = ? ORDER BY sold_at DESC', (user_id,)).fetchall()]
            
            provisions = []
            if seller:
                provisions = [dict(r) for r in conn.execute('SELECT * FROM gmails WHERE seller_id = ? ORDER BY created_at DESC', (seller['seller_id'],)).fetchall()]
                
            txns = [dict(r) for r in conn.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()]
            
            return {
                "profile": user,
                "seller_info": seller,
                "purchases": purchases,
                "provisions": provisions,
                "transactions": txns
            }
        finally:
            conn.close()
    
    def get_pending_withdrawals(self) -> List[Dict]:
        """Get all pending withdrawal requests"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT w.*, u.username, u.full_name, s.total_earnings
                FROM withdrawals w
                JOIN users u ON w.user_id = u.user_id
                JOIN sellers s ON w.seller_id = s.seller_id
                WHERE w.status = 'pending'
                ORDER BY w.created_at ASC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_pending_withdrawals_with_sales(self) -> List[Dict]:
        """Get pending withdrawals only from sellers who have sold Gmails"""
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT w.*, u.username, u.full_name, s.total_earnings,
                       COUNT(g.gmail_id) as total_sold
                FROM withdrawals w
                JOIN users u ON w.user_id = u.user_id
                JOIN sellers s ON w.seller_id = s.seller_id
                LEFT JOIN gmails g ON s.seller_id = g.seller_id AND g.status = 'sold'
                WHERE w.status = 'pending'
                GROUP BY w.withdrawal_id
                HAVING total_sold > 0
                ORDER BY w.created_at ASC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def process_withdrawal(self, withdrawal_id: int, admin_id: int, approved: bool = True) -> bool:
        """Process withdrawal request"""
        conn = self.get_connection()
        try:
            status = 'paid' if approved else 'rejected'
            conn.execute('''
                UPDATE withdrawals 
                SET status = ?, processed_at = ?, processed_by = ?
                WHERE withdrawal_id = ?
            ''', (status, datetime.now(), admin_id, withdrawal_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        conn = self.get_connection()
        try:
            stats = {}
            
            # User stats
            row = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()
            stats['total_users'] = row['count']
            
            # Gmail stats
            row = conn.execute("SELECT COUNT(*) as count FROM gmails WHERE status = 'available'").fetchone()
            stats['available_gmails'] = row['count']
            
            row = conn.execute("SELECT COUNT(*) as count FROM gmails WHERE status = 'sold'").fetchone()
            stats['sold_gmails'] = row['count']
            
            # Pending approvals
            row = conn.execute("SELECT COUNT(*) as count FROM sellers WHERE status = 'pending'").fetchone()
            stats['pending_sellers'] = row['count']
            
            row = conn.execute("SELECT COUNT(DISTINCT batch_id) as count FROM gmails WHERE status = 'pending'").fetchone()
            stats['pending_batches'] = row['count']
            
            row = conn.execute("SELECT COUNT(*) as count FROM withdrawals WHERE status = 'pending'").fetchone()
            stats['pending_withdrawals'] = row['count']
            
            # Revenue
            row = conn.execute("SELECT SUM(amount) as total FROM transactions WHERE status = 'success'").fetchone()
            stats['total_revenue'] = row['total'] or 0.0
            
            # Seller pending amount
            row = conn.execute("SELECT SUM(total_earnings) as total FROM sellers").fetchone()
            stats['seller_pending_payouts'] = row['total'] or 0.0
            
            return stats
        finally:
            conn.close()

    def get_time_based_analytics(self) -> Dict:
        """Get daily, weekly, monthly, and yearly transaction analytics (SQLite)"""
        analytics = {}
        periods = {
            'daily': "-1 days",
            'weekly': "-7 days",
            'monthly': "-30 days",
            'yearly': "-365 days"
        }
        
        conn = self.get_connection()
        try:
            for label, period in periods.items():
                row = conn.execute(f'''
                    SELECT SUM(amount) as total_amount, COUNT(*) as count 
                    FROM transactions 
                    WHERE status = 'success' AND created_at >= datetime('now', ?)
                ''', (period,)).fetchone()
                
                analytics[label] = {
                    "total_amount": row['total_amount'] or 0,
                    "count": row['count'] or 0
                }
            return analytics
        finally:
            conn.close()

    def save_support_message(self, user_id: int, message: str) -> bool:
        """Save support message from user"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT INTO support_messages (user_id, message, status)
                VALUES (?, ?, 'unread')
            ''', (user_id, message))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving support message: {e}")
            return False
        finally:
            conn.close()

    def get_support_messages(self, unread_only: bool = True) -> List[Dict]:
        """Get support messages for admin"""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM support_messages"
            if unread_only:
                query += " WHERE status = 'unread'"
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query).fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                user = self.get_user(msg['user_id'])
                msg['username'] = user['username'] if user else "Unknown"
                messages.append(msg)
            return messages
        finally:
            conn.close()

    def get_time_based_analytics(self) -> Dict:
        """Get time-based transaction analytics for dashboard"""
        from datetime import datetime, timedelta
        conn = self.get_connection()
        try:
            now = datetime.now()
            analytics = {}
            
            # Define time ranges
            ranges = {
                'daily': now - timedelta(days=1),
                'weekly': now - timedelta(days=7),
                'monthly': now - timedelta(days=30),
                'yearly': now - timedelta(days=365)
            }
            
            for label, start_date in ranges.items():
                result = conn.execute('''
                    SELECT 
                        COALESCE(SUM(amount), 0) as total_amount,
                        COUNT(*) as count
                    FROM transactions
                    WHERE status = 'success' AND created_at >= ?
                ''', (start_date,)).fetchone()
                
                analytics[label] = {
                    'total_amount': result['total_amount'] if result else 0,
                    'count': result['count'] if result else 0
                }
                
            return analytics
        finally:
            conn.close()

    def get_sellers_awaiting_payment(self) -> List[Dict]:
        """Get sellers who have sold Gmails"""
        import config
        conn = self.get_connection()
        try:
            # Get sellers with sold Gmails
            query = '''
                SELECT 
                    s.user_id,
                    u.username,
                    u.full_name,
                    COUNT(g.gmail_id) as sold_count,
                    MAX(g.sold_at) as last_sale_date,
                    s.upi_qr_path
                FROM sellers s
                JOIN users u ON s.user_id = u.user_id
                JOIN gmails g ON g.seller_id = s.seller_id
                WHERE g.status = 'sold'
                GROUP BY s.seller_id
                ORDER BY last_sale_date DESC
            '''
            
            rows = conn.execute(query).fetchall()
            result = []
            for row in rows:
                data = dict(row)
                data['amount_owed'] = data['sold_count'] * config.SELL_RATE
                result.append(data)
            return result
        finally:
            conn.close()


    def mark_seller_gmails_as_paid(self, user_id: int) -> int:
        """Count sold Gmails from a seller (no update needed without is_paid column)"""
        conn = self.get_connection()
        try:
            seller = self.get_seller(user_id)
            if not seller:
                return 0
            
            # Just count sold Gmails for this seller
            result = conn.execute('''
                SELECT COUNT(*) as count FROM gmails 
                WHERE seller_id = ? AND status = 'sold'
            ''', (seller['seller_id'],)).fetchone()
            
            return result['count'] if result else 0
        finally:
            conn.close()

    def get_all_purchases(self) -> List[Dict]:
        """Get all buyer purchases for admin panel"""
        conn = self.get_connection()
        try:
            query = '''
                SELECT 
                    g.gmail_id,
                    g.email,
                    g.sold_at,
                    buyer.user_id as buyer_id,
                    buyer.username as buyer_username,
                    seller_user.username as seller_username
                FROM gmails g
                LEFT JOIN users buyer ON g.buyer_id = buyer.user_id
                LEFT JOIN sellers s ON g.seller_id = s.seller_id
                LEFT JOIN users seller_user ON s.user_id = seller_user.user_id
                WHERE g.status = 'sold'
                ORDER BY g.sold_at DESC

            '''
            
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

# Global database instance
db = Database()
