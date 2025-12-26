"""
Flask Admin Dashboard for Gmail Marketplace Bot
Admin-only web interface to view users, sellers, and statistics
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from functools import wraps
import config

# Try MongoDB first, fallback to SQLite
try:
    from mongodb import db
    USE_MONGODB = True
except:
    from database import db
    USE_MONGODB = False

app = Flask(__name__)
app.secret_key = config.CASHFREE_SECRET_KEY  # Use for session encryption
CORS(app)

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or int(session['admin_id']) not in config.ADMIN_IDS:
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
    stats = db.get_stats()
    analytics = db.get_time_based_analytics()
    return render_template('dashboard.html', stats=stats, analytics=analytics)

@app.route('/pay/<session_id>')
def pay(session_id):
    """Bridge for Cashfree payment - opens checkout via SDK"""
    env = config.CASHFREE_ENV.lower()
    return render_template('pay.html', session_id=session_id, env=env)

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

@app.route('/api/users')
@admin_required
def get_users():
    """Get all users"""
    try:
        if USE_MONGODB:
            users = list(db.users.find({}, {'_id': 0}))
        else:
            conn = db.get_connection()
            users = [dict(row) for row in conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()]
            conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
