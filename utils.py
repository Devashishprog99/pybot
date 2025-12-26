"""
Utility functions for Gmail Marketplace Bot
"""
import re
import uuid
from datetime import datetime, timedelta
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import config

# ==================== VALIDATION ====================

def validate_gmail(gmail_str: str) -> bool:
    """Validate Gmail format (email:password)"""
    parts = gmail_str.split(':')
    if len(parts) != 2:
        return False
    
    email, password = parts
    email_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    
    if not re.match(email_pattern, email.strip()):
        return False
    
    if len(password.strip()) < 4:
        return False
    
    return True

def parse_gmail_list(text: str) -> list:
    """Parse Gmail list from text"""
    lines = text.strip().split('\n')
    gmails = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if validate_gmail(line):
            email, password = line.split(':', 1)
            gmails.append((email.strip(), password.strip()))
    
    return gmails


def check_gmail_credentials(email: str, password: str) -> bool:
    """Check if Gmail credentials are valid using format validation
    Note: IMAP validation disabled because Gmail now requires App Passwords
    which most sellers won't have. Buyers will verify accounts work."""
    # Just check format - email must be @gmail.com and password must be reasonable length
    if not email.lower().endswith('@gmail.com'):
        return False
    if len(password) < 4:  # Very basic check
        return False
    return True

# ==================== FORMATTING ====================

def format_currency(amount: float) -> str:
    """Format currency in Rs"""
    return f"₹{amount:.2f}"

def format_datetime(dt) -> str:
    """Format datetime"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%d %b %Y, %I:%M %p")

def generate_batch_id() -> str:
    """Generate unique batch ID"""
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

def generate_order_id() -> str:
    """Generate unique order ID for Cashfree"""
    return f"order_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

def format_countdown(seconds: int) -> str:
    """Format countdown timer"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

# ==================== KEYBOARD BUILDERS ====================

def build_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Build main menu keyboard"""
    keyboard = [
        ['💰 Wallet', '🛒 Buy Gmails'],
        ['📤 Sell Gmails', '📊 My Activity'],
        ['ℹ️ Help', '⬅️ Back']
    ]
    
    if is_admin:
        keyboard.append(['⚙️ Admin Panel'])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_wallet_keyboard() -> InlineKeyboardMarkup:
    """Build wallet keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Money", callback_data="wallet_add")],
        [InlineKeyboardButton("📜 Transaction History", callback_data="wallet_history")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_amount_keyboard() -> InlineKeyboardMarkup:
    """Build amount selection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("₹15", callback_data="amount_15"),
            InlineKeyboardButton("₹50", callback_data="amount_50"),
            InlineKeyboardButton("₹100", callback_data="amount_100")
        ],
        [
            InlineKeyboardButton("₹200", callback_data="amount_200"),
            InlineKeyboardButton("₹500", callback_data="amount_500")
        ],
        [InlineKeyboardButton("✏️ Custom Amount", callback_data="amount_custom")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="wallet_main"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

    return InlineKeyboardMarkup(keyboard)

def build_payment_keyboard(payment_link: str, order_id: str) -> InlineKeyboardMarkup:
    """Build payment keyboard with link and cancel"""
    keyboard = [
        [InlineKeyboardButton("💳 Pay Now", url=payment_link)],
        [InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_payment_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_buy_keyboard(available: int) -> InlineKeyboardMarkup:
    """Build quantity selection keyboard for buying"""
    keyboard = []
    
    # Quick select buttons
    quantities = [2, 5, 10, 20, 50]
    row = []
    for qty in quantities:
        if qty <= available:
            row.append(InlineKeyboardButton(str(qty), callback_data=f"buy_qty_{qty}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
    
    if row:
        keyboard.append(row)
    
    # Custom quantity and navigation
    keyboard.append([InlineKeyboardButton("✏️ Custom Quantity", callback_data="buy_custom")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_confirm_keyboard(action: str, data: str) -> InlineKeyboardMarkup:
    """Build confirmation keyboard"""
    back_target = "buy_main" if action == "purchase" else "wallet_main"
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}_{data}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=back_target),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_seller_wizard_keyboard(step: int) -> InlineKeyboardMarkup:
    """Build seller registration wizard keyboard"""
    keyboard = []
    
    if step == 1:
        # Step 1: After UPI upload
        keyboard.append([InlineKeyboardButton("Next ➡️", callback_data="seller_step2")])
    elif step == 2:
        # Step 2: After Gmail submission
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="seller_step1"),
            InlineKeyboardButton("Next ➡️", callback_data="seller_step3")
        ])
    elif step == 3:
        # Step 3: Review
        keyboard.append([
            InlineKeyboardButton("⬅️ Edit", callback_data="seller_step2"),
            InlineKeyboardButton("✅ Submit", callback_data="seller_submit")
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def build_my_activity_keyboard() -> InlineKeyboardMarkup:
    """Build my activity keyboard"""
    keyboard = [
        [InlineKeyboardButton("📦 My Purchases", callback_data="activity_purchases")],
        [InlineKeyboardButton("💵 My Sales", callback_data="activity_sales")],
        [InlineKeyboardButton("💳 Withdrawals", callback_data="activity_withdrawals")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_contact_keyboard() -> InlineKeyboardMarkup:
    """Build contact me keyboard"""
    keyboard = [
        [InlineKeyboardButton("📞 Contact Me (Support)", callback_data="contact_support")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_withdrawal_keyboard() -> InlineKeyboardMarkup:
    """Build withdrawal request keyboard"""
    keyboard = [
        [InlineKeyboardButton("💵 Request Withdrawal", callback_data="withdrawal_request")],
        [InlineKeyboardButton("⬅️ Back", callback_data="my_activity")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ADMIN KEYBOARDS ====================

def build_admin_keyboard() -> InlineKeyboardMarkup:
    """Build admin main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("👥 Users", callback_data="admin_users"),
            InlineKeyboardButton("📋 Sellers", callback_data="admin_sellers")
        ],
        [
            InlineKeyboardButton("📧 Gmails", callback_data="admin_gmails"),
            InlineKeyboardButton("💰 Withdrawals", callback_data="admin_withdrawals")
        ],
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_approval_keyboard(item_type: str, item_id: str) -> InlineKeyboardMarkup:
    """Build approval/rejection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{item_type}_{item_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{item_type}_{item_id}")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"admin_{item_type}s")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_admin_nav_keyboard(section: str) -> InlineKeyboardMarkup:
    """Build admin navigation keyboard"""
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_user_action_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Build user action keyboard"""
    keyboard = []
    
    if is_banned:
        keyboard.append([InlineKeyboardButton("✅ Unban User", callback_data=f"unban_{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user_id}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_users")])
    return InlineKeyboardMarkup(keyboard)

# ==================== MESSAGE TEMPLATES ====================

def welcome_message() -> str:
    """Welcome message for new users"""
    return f"""
🎉 **Welcome to Gmail Marketplace!**

Buy and sell Gmail accounts securely.

**For Buyers:**
• Buy Gmails starting from {config.MIN_BUY_QUANTITY} accounts @ {format_currency(config.BUY_RATE)} each
• Instant delivery to your account
• Secure wallet system

**For Sellers:**
• Sell Gmails @ {format_currency(config.SELL_RATE)} each (min {config.MIN_SELL_QUANTITY})
• Fast approval process
• Easy UPI withdrawals

Use the buttons below to get started! 👇
"""

def help_message() -> str:
    """Help message"""
    return f"""
📖 **How to Use**

**💰 Wallet:**
Add money to your wallet ({format_currency(config.MIN_WALLET_ADD)}-{format_currency(config.MAX_WALLET_ADD)})
Payment via Cashfree (5 min timer)

**🛒 Buy Gmails:**
1. Check available stock
2. Select quantity (min {config.MIN_BUY_QUANTITY})
3. Confirm purchase
4. Get credentials instantly

**📤 Sell Gmails:**
1. Upload UPI QR code
2. Submit Gmail list (email:password format)
3. Wait for admin approval
4. Earn {format_currency(config.SELL_RATE)} per Gmail

**Need help?** Contact support
"""

def format_gmail_credentials(gmails: list) -> str:
    """Format Gmail credentials for buyer"""
    message = "🎉 **Purchase Successful!**\n\n📧 **Your Gmail Accounts:**\n\n"
    
    for i, gmail in enumerate(gmails, 1):
        message += f"{i}. `{gmail['email']}:{gmail['password']}`\n"
    
    message += "\n⚠️ **Important:** Save these credentials securely. This message won't be shown again."
    return message
