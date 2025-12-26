import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

import io
import qrcode
import config
from database import db
from utils import (
    build_main_menu, welcome_message, help_message,
    build_wallet_keyboard, build_amount_keyboard, build_my_activity_keyboard,
    format_currency, format_countdown, build_contact_keyboard
)
from payment import payment_manager
from seller import seller_handler
from buyer import buyer_handler
from admin import admin_handler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Create or update user
    db.create_user(user.id, user.username or str(user.id), user.full_name or "User")
    
    # Check if admin
    is_admin = admin_handler.is_admin(user.id)
    
    await update.message.reply_text(
        welcome_message(),
        reply_markup=build_main_menu(is_admin),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if it's a menu button press - these should ALWAYS work, interrupting any flow
    menu_buttons = ["💰 Wallet", "🛒 Buy Gmails", "📤 Sell Gmails", "📊 My Activity", "ℹ️ Help", "⬅️ Back", "⚙️ Admin Panel"]
    if text in menu_buttons:
        # Clear all pending states
        for key in ['seller_step', 'withdrawal_step', 'awaiting_custom_amount', 'awaiting_quantity', 'awaiting_support_message', 'buy_quantity', 'pending_payment']:
            context.user_data.pop(key, None)
        
        # Handle the menu button
        if text == "💰 Wallet":
            await show_wallet(update, context)
            return
        elif text == "🛒 Buy Gmails":
            await buyer_handler.show_buy_menu(update, context)
            return
        elif text == "📤 Sell Gmails":
            await seller_handler.start_selling(update, context)
            return
        elif text == "📊 My Activity":
            await show_my_activity(update, context)
            return
        elif text == "ℹ️ Help":
            await update.message.reply_text(help_message(), parse_mode='Markdown')
            return
        elif text == "⬅️ Back":
            await update.message.reply_text(
                welcome_message(),
                reply_markup=build_main_menu(admin_handler.is_admin(user_id)),
                parse_mode='Markdown'
            )
            return
        elif text == "⚙️ Admin Panel":
            await admin_handler.show_admin_panel(update, context)
            return
    
    # Now handle awaiting states (only if NOT a menu button)
    if context.user_data.get('seller_step') == 1:
        # Waiting for UPI QR
        await update.message.reply_text("Please upload the UPI QR code image, not text.")
        return
    
    elif context.user_data.get('seller_step') == 2:
        # Waiting for Gmail list
        await seller_handler.handle_gmail_submission(update, context)
        return
    
    elif context.user_data.get('withdrawal_step'):
        # Waiting for withdrawal UPI QR
        await update.message.reply_text("Please upload the UPI QR code image.")
        return
    
    elif context.user_data.get('awaiting_custom_amount'):
        # Custom wallet amount
        await handle_custom_amount(update, context)
        return
    
    elif context.user_data.get('awaiting_quantity'):
        # Custom purchase quantity
        await buyer_handler.process_custom_quantity(update, context)
        return

    # Support message check
    if context.user_data.get('awaiting_support_message'):
        message = update.message.text
        if db.save_support_message(user_id, message):
            await update.message.reply_text("✅ Message sent successfully! Admin will review it soon.")
            for admin_id in config.ADMIN_IDS:
                try: await context.bot.send_message(admin_id, f"✉️ **New Support Message**\n\n👤 User ID: `{user_id}`\n💬 Message: {message}", parse_mode='Markdown')
                except: pass
        else:
            await update.message.reply_text("❌ Failed to send message. Please try again.")
        context.user_data.pop('awaiting_support_message', None)
        return

    # User ID detection for admins (forwarded messages or numeric IDs)
    if admin_handler.is_admin(user_id):
        # Check if forwarded message or numeric ID
        target_uid = None
        
        # Safe attribute check for different library versions
        fw_from = getattr(update.message, 'forward_from', None)
        fw_from_user = getattr(update.message, 'forward_from_user', None)
        
        if fw_from:
            target_uid = fw_from.id
        elif fw_from_user:
            target_uid = fw_from_user.id
        elif text.isdigit() and len(text) > 5:
            target_uid = int(text)
            
        if target_uid:
            await admin_handler.manage_user(update, context, target_uid)
            return
            
    else:
        await update.message.reply_text(
            "Please use the buttons below to interact with the bot.",
            reply_markup=build_main_menu(admin_handler.is_admin(user_id))
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads"""
    if context.user_data.get('seller_step') == 1:
        # UPI QR for seller registration (old flow, deprecated)
        await seller_handler.handle_upi_qr(update, context)
    elif context.user_data.get('seller_step') == 3:
        # UPI QR for new seller flow (after Gmail validation)
        await seller_handler.handle_upi_qr(update, context)
        # Then finalize the submission
        await seller_handler.finalize_submission(update, context)
    elif context.user_data.get('withdrawal_step'):
        # UPI QR for withdrawal
        await seller_handler.submit_withdrawal(update, context)
    else:
        await update.message.reply_text("I'm not sure what to do with this image.")

# ==================== WALLET HANDLERS ====================

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet information"""
    user_id = update.effective_user.id
    balance = db.get_wallet_balance(user_id)
    
    message = (
        f"💰 **Your Wallet**\n\n"
        f"Balance: {format_currency(balance)}\n\n"
        "Use the wallet to purchase Gmail accounts."
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=build_wallet_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=build_wallet_keyboard(),
            parse_mode='Markdown'
        )

async def show_add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show add money options"""
    query = update.callback_query
    await query.answer()
    
    message = (
        f"💵 **Add Money to Wallet**\n\n"
        f"Min: {format_currency(config.MIN_WALLET_ADD)}\n"
        f"Max: {format_currency(config.MAX_WALLET_ADD)}\n\n"
        "Select amount:"
    )
    
    await query.edit_message_text(
        message,
        reply_markup=build_amount_keyboard(),
        parse_mode='Markdown'
    )

async def initiate_direct_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Create a direct payment link and show Pay Now button"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Create the payment order
    result = await payment_manager.create_payment_order(user_id, float(amount))
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ Error creating payment: {result.get('error', 'Unknown error')}\n\n"
            "Please try again or contact support."
        )
        return
    
    order_id = result['order_id']
    payment_link = result['payment_link']
    context.user_data['pending_payment'] = order_id
    
    message = (
        f"💳 **Payment Ready**\n\n"
        f"💰 Amount: {format_currency(amount)}\n"
        f"🆔 Order ID: `{order_id}`\n\n"
        f"👇 **Click below to pay securely:**"
    )
    
    try:
        # Ensure URL has protocol for WebAppInfo
        if not payment_link.startswith('http'):
            payment_link = f"https://{payment_link}"

        keyboard = [
            [InlineKeyboardButton(f"💳 Pay {format_currency(amount)}", web_app=WebAppInfo(url=payment_link))],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        
        # Send payment message
        sent_msg = await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Monitor for payment success
        asyncio.create_task(monitor_payment(context, user_id, order_id, sent_msg.message_id))
            
    except Exception as e:
        logger.error(f"Failed to create payment: {e}")
        await query.edit_message_text(f"❌ Error initializing payment: {e}")

def generate_qr_image(data):
    """Generate QR code image in memory"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio)
    bio.seek(0)
    return bio

async def run_qr_timer(context, chat_id, message_id, duration):
    """Update message with countdown and then delete"""
    import asyncio
    remaining = duration
    
    # Store original caption parts or simplified one
    base_caption = (
        "💳 **Payment Initiated**\n"
        "👤 Paying to: **OTT4YOU**\n"
        "scan the QR code to pay instantly.\n\n"
        "👇 **Other Ways:**"
    )
    
    while remaining > 0:
        await asyncio.sleep(10) # Update every 10 seconds to avoid rate limits
        remaining -= 10
        if remaining <= 0: break
        
        try:
            current_caption = f"{base_caption}\n⏳ **Expires in: {remaining}s**"
            await context.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=current_caption,
                parse_mode='Markdown'
            )
        except Exception:
            # Message might be deleted or user blocked bot
            break
            
    # Time's up
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def monitor_payment(context: ContextTypes.DEFAULT_TYPE, user_id: int, order_id: str, message_id: int, qr_path: str = None):
    """Monitor payment status and update message"""
    import time
    start_time = time.time()
    timeout = config.PAYMENT_TIMEOUT
    
    while time.time() - start_time < timeout:
        if context.user_data.get('pending_payment') != order_id:
            return
        
        # Check payment status
        result = await payment_manager.check_payment_status(order_id)
        
        if result.get('success') and result.get('status') == 'SUCCESS':
            # Payment successful
            verified = await payment_manager.verify_payment(order_id)
            
            if verified:
                txn = db.get_transaction_by_order_id(order_id)
                
                # Try to delete the QR message if it still exists
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=message_id)
                except:
                    pass
                
                # Send FRESH success message with details
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ **Payment Successful!**\n"
                        f"👤 Paid to: **OTT4YOU**\n"
                        f"💰 Amount: {format_currency(txn['amount'])}\n"
                        f"🆔 Transaction ID: `{txn['txn_id']}`\n"
                        f"📅 Date: {str(txn['created_at'])[:16]}\n\n"
                        f"Funds have been added to your wallet!"
                    ),
                    parse_mode='Markdown'
                )
                context.user_data.pop('pending_payment', None)
                return
        
        elif result.get('status') == 'FAILED':
            # Payment failed
            try:
                await context.bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=message_id,
                    caption="❌ **Payment Failed**\n\nThe payment was declined or failed. Please try again."
                )
            except:
                # If QR message deleted, maybe send a text? User said "I DONT NEED ANY ERROR", so maybe silent is okay?
                # But let's notify if possible.
                await context.bot.send_message(chat_id=user_id, text="❌ **Payment Failed**")
                
            context.user_data.pop('pending_payment', None)
            return
        
        await asyncio.sleep(5)
    
    # Timeout
    await payment_manager.cancel_payment(order_id)
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=message_id)
    except:
        pass
        
    # Send timeout notification
    await context.bot.send_message(
        chat_id=user_id,
        text="⏱️ **Payment Timeout**\n\nThe payment request has expired.",
        parse_mode='Markdown'
    )
    context.user_data.pop('pending_payment', None)
    
    # Timeout
    await payment_manager.cancel_payment(order_id)
    await context.bot.edit_message_text(
        "⏱️ **Payment Timeout**\n\nThe payment link has expired. Please try again.",
        chat_id=user_id,
        message_id=message_id
    )
    context.user_data.pop('pending_payment', None)

async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom amount input"""
    try:
        amount = float(update.message.text.strip())
        
        if amount < config.MIN_WALLET_ADD or amount > config.MAX_WALLET_ADD:
            await update.message.reply_text(
                f"❌ Amount must be between {format_currency(config.MIN_WALLET_ADD)} "
                f"and {format_currency(config.MAX_WALLET_ADD)}"
            )
            return
        
        context.user_data.pop('awaiting_custom_amount', None)
        
        # Create fake callback query to reuse the handler
        fake_update = type('obj', (object,), {
            'callback_query': type('obj', (object,), {
                'answer': lambda: None,
                'edit_message_text': update.message.reply_text
            })(),
            'effective_user': update.effective_user
        })()
        
        await process_amount_selection(fake_update, context, int(amount))
        
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show transaction history"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    txns = db.get_user_transactions(user_id, 10)
    
    if not txns:
        await query.edit_message_text("📜 No transactions yet!")
        return
    
    message = "📜 **Transaction History**\n\n"
    
    for txn in txns:
        status_emoji = "✅" if txn['status'] == 'success' else "❌" if txn['status'] == 'failed' else "⏳"
        message += f"{status_emoji} {txn['description']}\n"
        message += f"   {format_currency(abs(txn['amount']))} • {str(txn['created_at'])[:16]}\n\n"
    
    await query.edit_message_text(message, parse_mode='Markdown')

# ==================== ACTIVITY HANDLERS ====================

async def show_my_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show my activity menu"""
    message = "📊 **My Activity**\n\nSelect an option:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=build_my_activity_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=build_my_activity_keyboard(),
            parse_mode='Markdown'
        )

# ==================== CALLBACK QUERY HANDLER ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # Wallet callbacks
    if data == "wallet_add":
        await show_add_money(update, context)
    elif data == "wallet_history":
        await show_transaction_history(update, context)
    elif data.startswith("amount_"):
        if data == "amount_custom":
            await query.answer()
            context.user_data['awaiting_custom_amount'] = True
            await query.edit_message_text(
                f"✏️ Enter custom amount ({format_currency(config.MIN_WALLET_ADD)} - {format_currency(config.MAX_WALLET_ADD)}):"
            )
        else:
            amount = int(data.split('_')[1])
            await initiate_direct_payment(update, context, amount)
    elif data.startswith("cancel_payment_"):
        order_id = data.replace("cancel_payment_", "")
        await payment_manager.cancel_payment(order_id)
        context.user_data.pop('pending_payment', None)
        await query.edit_message_text("❌ Payment cancelled.")
    
    # Buy callbacks
    elif data == "buy_gmails":
        await buyer_handler.show_buy_menu(update, context)
    elif data.startswith("buy_qty_"):
        qty = int(data.split('_')[2])
        await buyer_handler.handle_quantity_selection(update, context, qty)
    elif data == "buy_custom":
        await buyer_handler.handle_custom_quantity(update, context)
    elif data.startswith("confirm_purchase_"):
        await buyer_handler.process_purchase(update, context)
    
    # Activity callbacks
    elif data == "my_activity":
        await show_my_activity(update, context)
    elif data == "activity_purchases":
        await buyer_handler.show_purchases(update, context)
    elif data == "activity_sales":
        await seller_handler.show_sales_stats(update, context)
    elif data == "activity_withdrawals" or data == "withdrawal_request":
        await seller_handler.request_withdrawal(update, context)
    
    # Seller callbacks
    elif data == "seller_submit":
        await seller_handler.submit_for_approval(update, context)
    
    # Admin callbacks
    elif data == "admin_panel":
        await admin_handler.show_admin_panel(update, context)
    elif data == "admin_dashboard":
        await admin_handler.show_dashboard(update, context)
    elif data == "admin_sellers":
        await admin_handler.show_pending_sellers(update, context)
    elif data == "admin_gmails":
        await admin_handler.show_pending_gmails(update, context)
    elif data == "admin_withdrawals":
        await admin_handler.show_pending_withdrawals(update, context)
    elif data.startswith("approve_seller_"):
        seller_id = int(data.split('_')[2])
        await admin_handler.approve_seller(update, context, seller_id)
    elif data.startswith("reject_seller_"):
        seller_id = int(data.split('_')[2])
        await admin_handler.reject_seller(update, context, seller_id)
    elif data.startswith("approve_batch_"):
        batch_id = data.replace("approve_batch_", "")
        await admin_handler.approve_gmail_batch(update, context, batch_id)
    elif data.startswith("reject_batch_"):
        batch_id = data.replace("reject_batch_", "")
        await admin_handler.reject_gmail_batch(update, context, batch_id)
    elif data == "admin_users":
        await admin_handler.show_users(update, context)
    elif data.startswith("ban_"):
        user_id = int(data.split('_')[1])
        await admin_handler.toggle_ban(update, context, user_id, True)
    elif data.startswith("unban_"):
        user_id = int(data.split('_')[1])
        await admin_handler.toggle_ban(update, context, user_id, False)
    elif data.startswith("approve_withdrawal_"):
        withdrawal_id = int(data.split('_')[2])
        await admin_handler.approve_withdrawal(update, context, withdrawal_id)
    elif data.startswith("reject_withdrawal_"):
        withdrawal_id = int(data.split('_')[2])
        await admin_handler.reject_withdrawal(update, context, withdrawal_id)
    
    # Support callbacks
    elif data == "contact_support":
        context.user_data['awaiting_support_message'] = True
        await query.edit_message_text(
            "📞 **Contact Support**\n\n"
            "Please write your **entire message in one text only**.\n"
            "Include your order details or question.",
            reply_markup=build_contact_keyboard(),
            parse_mode='Markdown'
        )
    
    # Global Navigation
    elif data == "cancel":
        # Reset all states
        for key in ['seller_step', 'withdrawal_step', 'awaiting_custom_amount', 'awaiting_quantity', 'awaiting_support_message', 'buy_quantity', 'pending_payment']:
            context.user_data.pop(key, None)
        
        # Show welcome message with main menu
        await query.edit_message_text(
            welcome_message(),
            reply_markup=build_main_menu(admin_handler.is_admin(user_id)),
            parse_mode='Markdown'
        )

    elif data == "main_menu":
        # Clean state
        for key in ['seller_step', 'withdrawal_step', 'awaiting_custom_amount', 'awaiting_quantity', 'awaiting_support_message']:
            context.user_data.pop(key, None)
        
        # Show welcome message with main menu
        await query.edit_message_text(
            welcome_message(),
            reply_markup=build_main_menu(admin_handler.is_admin(user_id)),
            parse_mode='Markdown'
        )

    elif data == "wallet_main":
        await show_wallet(update, context)
    
    elif data == "buy_main":
        await buyer_handler.show_buy_menu(update, context)

    elif data == "my_activity":
        await show_my_activity(update, context)

    elif data == "seller_step1":
        context.user_data['seller_step'] = 1
        await seller_handler.start_selling(update, context)
    else:
        await query.answer("Feature not implemented yet!")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    import traceback
    traceback.print_exc()
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            f"❌ An error occurred: {context.error}"
        )

# ==================== MAIN ====================

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Diagnostic command for admins"""
    user_id = update.effective_user.id
    if not admin_handler.is_admin(user_id):
        return
        
    dash_url = config.DASHBOARD_URL or "Not Set"
    use_bridge = "✅ ENABLED" if config.USE_PAYMENT_BRIDGE else "❌ DISABLED (Direct Links)"
    
    # Masked keys for safety
    app_id = config.CASHFREE_APP_ID
    masked_id = f"{app_id[:4]}...{app_id[-4:]}" if len(app_id) > 4 else "NOT SET"
    
    # Environment Mismatch Detection
    env_status = "✅ Mode & Keys Match"
    env_warning = ""
    is_test_key = app_id.upper().startswith("TEST")
    is_prod_env = config.CASHFREE_ENV.upper() == "PRODUCTION"
    
    if is_prod_env and is_test_key:
        env_status = "⚠️ **MISMATCH DETECTED**"
        env_warning = "\n⚠️ **WARNING**: You are in `PRODUCTION` mode but using a `TEST` App ID. Standard payments will fail with 'Session Invalid'."
    elif not is_prod_env and not is_test_key:
        env_status = "⚠️ **MISMATCH DETECTED**"
        env_warning = "\n⚠️ **WARNING**: You are in `TEST` mode but using what looks like a `PRODUCTION` App ID."

    # Check for empty keys
    status = "✅ OK"
    if not config.CASHFREE_APP_ID or not config.CASHFREE_SECRET_KEY:
        status = "❌ KEYS MISSING"
        
    message = (
        "⚙️ **System Configuration Check**\n\n"
        f"📋 Key Status: `{status}`\n"
        f"🏁 **Mode**: `{config.CASHFREE_ENV}`\n"
        f"⚖️ **Env Match**: {env_status}\n"
        f"🆔 **App ID**: `{masked_id}`\n"
        f"🌐 **Dashboard**: `{dash_url}`\n"
        f"🌉 **Bridge**: `{use_bridge}`\n"
        f"{env_warning}\n"
        "💡 *Tip: If you just changed Railway variables, make sure to RESTART the bot deployment to apply them.*"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View last payment API response for debugging"""
    user_id = update.effective_user.id
    if not admin_handler.is_admin(user_id):
        return
        
    last_resp = payment_manager.get_last_response()
    
    await update.message.reply_text(
        f"📋 **Last Payment API Response**\n\n```\n{last_resp}\n```",
        parse_mode='Markdown'
    )

def main():
    """Start the bot"""
    try:
        # Validate configuration
        config.validate_config()
        
        # Create application
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("check", check_command))
        app.add_handler(CommandHandler("logs", logs_command))
        app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(help_message(), parse_mode='Markdown')))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(handle_callback))
        
        # Error handler
        app.add_error_handler(error_handler)
        
        # Start bot
        logger.info("Bot started successfully!")
        print(">> Bot is running...")
        print(f">> Environment: {config.CASHFREE_ENV}")
        print(f">> Admin IDs: {config.ADMIN_IDS}")
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f">> Error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set.")

if __name__ == "__main__":
    main()
