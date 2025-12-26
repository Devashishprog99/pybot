"""
Configuration management for Gmail Marketplace Bot
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(uid.strip()) for uid in os.getenv('ADMIN_IDS', '').split(',') if uid.strip()]

# Cashfree Configuration
CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID', '').strip()
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY', '').strip()
CASHFREE_ENV = os.getenv('CASHFREE_ENV', 'TEST').strip().upper()  # TEST or PRODUCTION

# Dashboard Configuration
DASHBOARD_URL = os.getenv('DASHBOARD_URL', '').strip()
USE_PAYMENT_BRIDGE = os.getenv('USE_PAYMENT_BRIDGE', 'TRUE').strip().upper() == 'TRUE'

# Pricing Configuration
SELL_RATE = float(os.getenv('SELL_RATE', 9.0))
BUY_RATE = float(os.getenv('BUY_RATE', 15.0))
MIN_SELL_QUANTITY = int(os.getenv('MIN_SELL_QUANTITY', 2))
MIN_BUY_QUANTITY = int(os.getenv('MIN_BUY_QUANTITY', 2))

# Wallet Configuration
MIN_WALLET_ADD = int(os.getenv('MIN_WALLET_ADD', 15))
MAX_WALLET_ADD = int(os.getenv('MAX_WALLET_ADD', 500))

# Payment Timer (in seconds)
PAYMENT_TIMEOUT = int(os.getenv('PAYMENT_TIMEOUT', 900))

# Database Configuration - MongoDB
MONGODB_URI = os.getenv('MONGODB_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'gmail_marketplace')
DATABASE_PATH = os.getenv('DATABASE_PATH', 'gmail_marketplace.db')  # Fallback to SQLite

# Validation
def validate_config():
    """Validate required configuration"""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is required")
    
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS is required")
    
    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
        errors.append("Cashfree credentials (CASHFREE_APP_ID, CASHFREE_SECRET_KEY) are required")
    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"- {err}" for err in errors))
    
    return True
