"""
Gmail Marketplace Telegram Bot
Main application file
"""
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

import config
from mongodb import db
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
    text = update.message.text
    user_id = update.effective_user.id
    
    # Check user context for active flows
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

    elif context.user_data.get('awaiting_support_message'):
        # Customer support message
        user_id = update.effective_user.id
        message = update.message.text
        if db.save_support_message(user_id, message):
            await update.message.reply_text("✅ Message sent successfully! Admin will review it soon.")
            # Notify admin
            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"✉️ **New Support Message**\n\n"
                        f"👤 User ID: `{user_id}`\n"
                        f"💬 Message: {message}",
                        parse_mode='Markdown'
                    )
                except: pass
        else:
            await update.message.reply_text("❌ Failed to send message. Please try again.")
        context.user_data.pop('awaiting_support_message', None)
        return
    
    # Menu button handlers
    if text == "💰 Wallet":
        await show_wallet(update, context)
    elif text == "🛒 Buy Gmails":
        await buyer_handler.show_buy_menu(update, context)
    elif text == "📤 Sell Gmails":
        await seller_handler.start_selling(update, context)
    elif text == "📊 My Activity":
        await show_my_activity(update, context)
    elif text == "ℹ️ Help":
        await update.message.reply_text(help_message(), parse_mode='Markdown')
    elif text == "⚙️ Admin Panel":
        await admin_handler.show_admin_panel(update, context)
    else:
        await update.message.reply_text(
            "Please use the buttons below to interact with the bot.",
            reply_markup=build_main_menu(admin_handler.is_admin(user_id))
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads"""
    if context.user_data.get('seller_step') == 1:
        # UPI QR for seller registration
        await seller_handler.handle_upi_qr(update, context)
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
            reply_markup=build_wallet_keyboard(balance),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=build_wallet_keyboard(balance),
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

async def process_amount_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Process amount selection and create payment"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Create QR payment order
    result = await payment_manager.create_qr_payment(user_id, float(amount))
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ Error creating payment: {result.get('error', 'Unknown error')}"
        )
        return
    
    order_id = result['order_id']
    qr_path = result['qr_path']
    
    # Save order_id in context for monitoring
    context.user_data['pending_payment'] = order_id
    
    message = (
        f"💳 **Pay via UPI QR**\n\n"
        f"Amount: {format_currency(amount)}\n"
        f"⏱️ Expires in: 5:00\n\n"
        "1. Scan the QR code below\n"
        "2. Complete the payment in your UPI app\n"
        "3. Wait here for confirmation\n\n"
        "⚠️ Do not close this chat until confirmed!"
    )
    
    # Send QR as photo
    sent_photo = await query.message.reply_photo(
        photo=open(qr_path, 'rb'),
        caption=message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_payment_{order_id}")]])
    )
    
    await query.message.delete()
    
    # Start payment monitoring
    asyncio.create_task(monitor_payment(context, user_id, order_id, sent_photo.message_id, qr_path))

async def monitor_payment(context: ContextTypes.DEFAULT_TYPE, user_id: int, order_id: str, message_id: int, qr_path: str):
    """Monitor payment status and update message"""
    import time
    
    start_time = time.time()
    timeout = config.PAYMENT_TIMEOUT
    
    while time.time() - start_time < timeout:
        # Check if cancelled
        if context.user_data.get('pending_payment') != order_id:
            if os.path.exists(qr_path): os.remove(qr_path)
            return
        
        # Check payment status
        result = await payment_manager.check_payment_status(order_id)
        
        if result.get('success') and result.get('status') == 'SUCCESS':
            # Payment successful
            verified = await payment_manager.verify_payment(order_id)
            
            if verified:
                txn = db.get_transaction_by_order_id(order_id)
                await context.bot.delete_message(chat_id=user_id, message_id=message_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ **Payment Successful!**\n\n{format_currency(txn['amount'])} added to your wallet!",
                    parse_mode='Markdown'
                )
                context.user_data.pop('pending_payment', None)
                if os.path.exists(qr_path): os.remove(qr_path)
                return
        
        elif result.get('status') == 'FAILED':
            # Payment failed
            await context.bot.edit_message_caption(
                chat_id=user_id,
                message_id=message_id,
                caption="❌ **Payment Failed**\n\nPlease try again."
            )
            context.user_data.pop('pending_payment', None)
            if os.path.exists(qr_path): os.remove(qr_path)
            return
        
        await asyncio.sleep(5)
    
    # Timeout
    await payment_manager.cancel_payment(order_id)
    await context.bot.edit_message_caption(
        chat_id=user_id,
        message_id=message_id,
        caption="⏱️ **Payment Timeout**\n\nThe payment has expired. Please try again."
    )
    context.user_data.pop('pending_payment', None)
    if os.path.exists(qr_path): os.remove(qr_path)
    
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
        message += f"   {format_currency(abs(txn['amount']))} • {txn['created_at'][:16]}\n\n"
    
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
            await process_amount_selection(update, context, amount)
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
            parse_mode='Markdown'
        )
    else:
        await query.answer("Feature not implemented yet!")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )

# ==================== MAIN ====================

def main():
    """Start the bot"""
    try:
        # Validate configuration
        config.validate_config()
        
        # Create application
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
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
