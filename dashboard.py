"""
Flask Admin Dashboard for Gmail Marketplace Bot
Admin-only web interface to view users, sellers, and statistics
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from functools import wraps
import config

# Always use SQLite database (same as Telegram bot)
from database import db
import config

# Database path logging for debugging
import os
print("=" * 50)
print("WEB DASHBOARD STARTING - Database Info:")
print(f"DATABASE_PATH: {config.DATABASE_PATH}")
print(f"DB instance path: {db.db_path}")
print(f"Absolute path: {os.path.abspath(db.db_path)}")
print(f"File exists: {os.path.exists(db.db_path)}")
print("=" * 50)

app = Flask(__name__)
app.secret_key = config.CASHFREE_SECRET_KEY or "dev-secret-key-123" # Fallback if key missing
CORS(app)

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if 'admin_id' not in session or int(session['admin_id']) not in config.ADMIN_IDS:
                return redirect(url_for('login'))
        except (ValueError, TypeError, KeyError):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        if admin_id and int(admin_id) in config.ADMIN_IDS:
            session['admin_id'] = admin_id
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid Admin ID")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@admin_required
def dashboard():
    try:
        stats = db.get_stats()
        analytics = db.get_time_based_analytics()
        return render_template('dashboard.html', stats=stats, analytics=analytics)
    except Exception as e:
        print(f"DASHBOARD ERROR: {e}")
        return f"<h3>Unexpected error</h3><p>{str(e)}</p>", 500

# ==================== ADMIN MANAGEMENT ROUTES ====================

@app.route('/admin/users')
@admin_required
def admin_users():
    """View all users"""
    try:
        users = db.get_all_users()
        return render_template('admin_users.html', users=users)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading users</h3><p>{str(e)}</p>", 500

@app.route('/admin/broadcast', methods=['GET', 'POST'])
@admin_required
def admin_broadcast():
    """Send broadcast message to all users"""
    if request.method == 'GET':
        users = db.get_all_users()
        return render_template('admin_broadcast.html', user_count=len(users))
    
    # POST - Send broadcast
    try:
        import requests
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        users = db.get_all_users()
        sent = 0
        failed = 0
        
        # Send via Telegram Bot API
        bot_token = config.TELEGRAM_BOT_TOKEN
        for user in users:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': user['user_id'],
                    'text': message,
                    'parse_mode': 'Markdown'
                }
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code == 200:
                    sent += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        return jsonify({
            'success': True, 
            'message': f'Broadcast sent! {sent} delivered, {failed} failed',
            'sent': sent,
            'failed': failed
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/sellers')
@admin_required
def admin_sellers():
    """View all sellers with approve/reject options"""
    try:
        sellers = db.get_all_sellers_with_stats()
        return render_template('admin_sellers.html', sellers=sellers)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading sellers</h3><p>{str(e)}</p>", 500

@app.route('/admin/sellers/<int:seller_id>/approve', methods=['POST'])
@admin_required
def approve_seller_web(seller_id):
    """Approve a seller"""
    try:
        admin_id = int(session['admin_id'])
        db.approve_seller(seller_id, admin_id, approved=True)
        return jsonify({'success': True, 'message': 'Seller approved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/sellers/<int:seller_id>/reject', methods=['POST'])
@admin_required
def reject_seller_web(seller_id):
    """Reject a seller"""
    try:
        admin_id = int(session['admin_id'])
        db.approve_seller(seller_id, admin_id, approved=False)
        return jsonify({'success': True, 'message': 'Seller rejected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/gmails')
@admin_required
def admin_gmails():
    """View pending Gmail batches"""
    try:
        batches = db.get_pending_gmail_batches()
        return render_template('admin_gmails.html', batches=batches)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading Gmail batches</h3><p>{str(e)}</p>", 500

@app.route('/admin/gmails/<batch_id>/approve', methods=['POST'])
@admin_required
def approve_gmail_batch_web(batch_id):
    """Approve a Gmail batch"""
    try:
        admin_id = int(session['admin_id'])
        db.approve_gmail_batch(batch_id, admin_id)
        return jsonify({'success': True, 'message': 'Gmail batch approved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/gmails/<batch_id>/reject', methods=['POST'])
@admin_required
def reject_gmail_batch_web(batch_id):
    """Reject a Gmail batch"""
    try:
        admin_id = int(session['admin_id'])
        db.reject_gmail_batch(batch_id, admin_id)
        return jsonify({'success': True, 'message': 'Gmail batch rejected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/buyers')
@admin_required
def admin_buyers():
    """View all buyer purchases"""
    try:
        purchases = db.get_all_purchases()
        return render_template('admin_buyers.html', purchases=purchases)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading purchases</h3><p>{str(e)}</p>", 500

@app.route('/admin/payments')
@admin_required
def admin_payments():
    """View sellers awaiting payment"""
    try:
        payments = db.get_sellers_awaiting_payment()
        return render_template('admin_payments.html', payments=payments)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading pending payments</h3><p>{str(e)}</p>", 500

@app.route('/admin/payments/<int:user_id>/mark_paid', methods=['POST'])
@admin_required
def mark_payment_web(user_id):
    """Mark seller as paid"""
    try:
        count = db.mark_seller_gmails_as_paid(user_id)
        return jsonify({'success': True, 'message': f'{count} Gmail(s) marked as paid', 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== SUPPORT DESK ====================

@app.route('/admin/support')
@admin_required
def admin_support():
    """View all support tickets"""
    try:
        status_filter = request.args.get('status', None)
        tickets = db.get_all_tickets(status_filter)
        return render_template('admin_support.html', tickets=tickets, current_status=status_filter)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading tickets</h3><p>{str(e)}</p>", 500

@app.route('/admin/support/<int:ticket_id>/reply', methods=['POST'])
@admin_required
def reply_ticket(ticket_id):
    """Reply to a support ticket and notify user via Telegram"""
    try:
        import requests
        data = request.get_json()
        reply = data.get('reply', '')
        status = data.get('status', 'resolved')
        
        # Get ticket info to find user_id
        tickets = db.get_all_tickets()
        ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)
        
        if not ticket:
            return jsonify({'success': False, 'error': 'Ticket not found'}), 404
        
        # Update ticket in database
        db.update_ticket_status(ticket_id, status, reply)
        
        # Send Telegram message to user
        user_id = ticket['user_id']
        if reply:
            try:
                bot_token = config.TELEGRAM_BOT_TOKEN
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': user_id,
                    'text': f"💬 **Reply to Ticket #{ticket_id}**\n\nAdmin says:\n{reply}\n\nThank you for contacting support!",
                    'parse_mode': 'Markdown'
                }
                requests.post(url, json=payload, timeout=5)
            except:
                pass
        
        return jsonify({'success': True, 'message': 'Reply sent to user via Telegram'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== INVENTORY ====================

@app.route('/admin/inventory')
@admin_required
def admin_inventory():
    """View Gmail inventory stats"""
    try:
        stats = db.get_stats()
        sellers = db.get_all_sellers_with_stats()
        return render_template('admin_inventory.html', stats=stats, sellers=sellers)
    except Exception as e:
        print(f"ERROR: {e}")
        return f"<h3>Error loading inventory</h3><p>{str(e)}</p>", 500

@app.route('/pay/<session_id>')
@app.route('/pay/<env_override>/<session_id>')
def pay(session_id, env_override=None):
    """Bridge for Cashfree payment - opens checkout via SDK"""
    # Use override from URL if present, otherwise fallback to config
    env = (env_override or config.CASHFREE_ENV).upper()
    print(f"DEBUG: Payment Bridge accessed. Session: {session_id[:10]}... Mode: {env} (Override: {env_override})")
    return render_template('pay.html', session_id=session_id, env=env.lower())

@app.route('/diag')
def diag():
    """Diagnostic route to check environment setup"""
    return jsonify({
        "CASHFREE_ENV": config.CASHFREE_ENV.upper(),
        "DASHBOARD_URL": config.DASHBOARD_URL,
        "ADMIN_COUNT": len(config.ADMIN_IDS),
        "STATUS": "OK"
    })

@app.route('/api/analytics')
@admin_required
def get_analytics():
    """Get time-based transaction analytics"""
    analytics = db.get_time_based_analytics()
    return jsonify(analytics)

@app.route('/api/support')
@admin_required
def get_support():
    """Get support messages"""
    messages = db.get_support_messages(unread_only=False)
    return jsonify(messages)

@app.route('/close')
def close_webapp():
    """Helper page to close WebApp"""
    return """
    <html>
    <head>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
    </head>
    <body onload="Telegram.WebApp.close()">
        <p>Closing...</p>
    </body>
    </html>
    """

@app.route('/api/users')
@admin_required
def get_users_api():
    """Get all users with statistics"""
    users = db.get_users_with_stats()
    return jsonify(users)

@app.route('/api/user/<int:user_id>')
@admin_required
def get_user_detail_api(user_id):
    """Get detailed statistics for a specific user"""
    detail = db.get_user_detail(user_id)
    if not detail:
        return jsonify({"error": "User not found"}), 404
    return jsonify(detail)

@app.route('/user/<int:user_id>')
@admin_required
def user_detail_view(user_id):
    """Render user detail page"""
    return render_template('user_detail.html', user_id=user_id)

@app.route('/api/sellers')
@admin_required
def get_sellers():
    """Get all sellers with stats"""
    sellers = db.get_all_sellers_with_stats()
    return jsonify(sellers)

@app.route('/api/gmails')
@admin_required
def get_gmails():
    """Get Gmail statistics"""
    try:
        if USE_MONGODB:
            gmails = list(db.gmails.find({}, {'password': 0}))  # Don't expose passwords
            for g in gmails:
                g['_id'] = str(g['_id'])
        else:
            conn = db.get_connection()
            gmails = [dict(row) for row in conn.execute('SELECT gmail_id, seller_id, email, status, batch_id, buyer_id, created_at, sold_at FROM gmails').fetchall()]
            conn.close()
        return jsonify(gmails)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transactions')
@admin_required
def get_transactions():
    """Get all transactions"""
    try:
        if USE_MONGODB:
            txns = list(db.transactions.find({}).sort('created_at', -1).limit(100))
            for t in txns:
                t['_id'] = str(t['_id'])
        else:
            conn = db.get_connection()
            txns = [dict(row) for row in conn.execute('SELECT * FROM transactions ORDER BY created_at DESC LIMIT 100').fetchall()]
            conn.close()
        return jsonify(txns)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/withdrawals')
@admin_required
def get_withdrawals():
    """Get all withdrawal requests"""
    withdrawals = db.get_pending_withdrawals()
    return jsonify(withdrawals)

@app.route('/api/stats')
@admin_required
def get_stats():
    """Get system statistics"""
    stats = db.get_stats()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
