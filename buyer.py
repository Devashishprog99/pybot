"""
Buyer Module - Handle purchase operations
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils import (
    format_currency, build_buy_keyboard, build_confirm_keyboard,
    format_gmail_credentials, build_contact_keyboard
)
import config
from mongodb import db

class BuyerHandler:
    
    @staticmethod
    async def show_buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show buy menu with available stock"""
        user_id = update.effective_user.id
        
        # Get available count
        available = db.get_available_gmails_count()
        
        if available < config.MIN_BUY_QUANTITY:
            message = (
                "❌ **Insufficient Stock**\n\n"
                f"Available: {available} Gmails\n"
                f"Minimum required: {config.MIN_BUY_QUANTITY}\n\n"
                "Please check back later!"
            )
            
            if update.callback_query:
                await update.callback_query.edit_message_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
            return
        
        # Get user wallet balance
        balance = db.get_wallet_balance(user_id)
        min_cost = config.MIN_BUY_QUANTITY * config.BUY_RATE
        
        message = (
            "🛒 **Buy Gmail Accounts**\n\n"
            f"📦 Available: {available} Gmails\n"
            f"💰 Price: {format_currency(config.BUY_RATE)} per Gmail\n"
            f"📊 Minimum: {config.MIN_BUY_QUANTITY} Gmails\n\n"
            f"👛 Your Balance: {format_currency(balance)}\n"
            f"💵 Minimum Cost: {format_currency(min_cost)}\n\n"
            "Select quantity:"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=build_buy_keyboard(available),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=build_buy_keyboard(available),
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def handle_quantity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity: int):
        """Handle quantity selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Validate quantity
        available = db.get_available_gmails_count()
        
        if quantity < config.MIN_BUY_QUANTITY:
            await query.answer(f"❌ Minimum {config.MIN_BUY_QUANTITY} Gmails required!", show_alert=True)
            return
        
        if quantity > available:
            await query.answer(f"❌ Only {available} Gmails available!", show_alert=True)
            return
        
        # Calculate cost
        total_cost = quantity * config.BUY_RATE
        balance = db.get_wallet_balance(user_id)
        
        if balance < total_cost:
            await query.edit_message_text(
                f"❌ **Insufficient Balance**\n\n"
                f"Required: {format_currency(total_cost)}\n"
                f"Your Balance: {format_currency(balance)}\n"
                f"Shortfall: {format_currency(total_cost - balance)}\n\n"
                "Please add money to your wallet first!",
                parse_mode='Markdown'
            )
            return
        
        # Show confirmation
        context.user_data['buy_quantity'] = quantity
        
        message = (
            "✅ **Confirm Purchase**\n\n"
            f"📧 Quantity: {quantity} Gmails\n"
            f"💰 Price: {format_currency(config.BUY_RATE)} × {quantity}\n"
            f"💵 Total: {format_currency(total_cost)}\n\n"
            f"👛 Current Balance: {format_currency(balance)}\n"
            f"📊 After Purchase: {format_currency(balance - total_cost)}\n\n"
            "Confirm to proceed:"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=build_confirm_keyboard('purchase', str(quantity)),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process Gmail purchase"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        quantity = context.user_data.get('buy_quantity')
        
        if not quantity:
            await query.edit_message_text("❌ Error: Invalid purchase request.")
            return
        
        # Double-check availability and balance
        available = db.get_available_gmails_count()
        balance = db.get_wallet_balance(user_id)
        total_cost = quantity * config.BUY_RATE
        
        if quantity > available:
            await query.edit_message_text(f"❌ Only {available} Gmails available now!")
            return
        
        if balance < total_cost:
            await query.edit_message_text("❌ Insufficient balance!")
            return
        
        # Purchase Gmails
        gmails = db.purchase_gmails(user_id, quantity)
        
        if not gmails:
            await query.edit_message_text("❌ Purchase failed. Please try again.")
            return
        
        # Deduct from wallet
        db.update_wallet(user_id, -total_cost)
        
        # Create transaction record
        db.create_transaction(
            user_id=user_id,
            txn_type='purchase',
            amount=-total_cost,
            description=f"Purchased {quantity} Gmail(s)"
        )
        db.update_transaction_status(
            db.get_user_transactions(user_id, 1)[0]['txn_id'],
            'success'
        )
        
        # Update seller earnings
        for gmail in gmails:
            seller_id = gmail['seller_id']
            db.update_seller_earnings(seller_id, config.SELL_RATE)
        
        # Send credentials
        credentials_msg = format_gmail_credentials(gmails)
        
        await query.edit_message_text(
            f"✅ **Purchase Successful!**\n\n"
            f"📧 Purchased: {quantity} Gmails\n"
            f"💰 Paid: {format_currency(total_cost)}\n\n"
            "Sending credentials..."
        )
        
        # Send credentials in a separate message
        await context.bot.send_message(
            user_id,
            credentials_msg,
            reply_markup=build_contact_keyboard(),
            parse_mode='Markdown'
        )
        
        # Clear context
        context.user_data.pop('buy_quantity', None)
    
    @staticmethod
    async def show_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's purchase history"""
        user_id = update.effective_user.id
        query = update.callback_query
        await query.answer()
        
        purchases = db.get_user_purchases(user_id)
        
        if not purchases:
            await query.edit_message_text(
                "📦 **My Purchases**\n\n"
                "You haven't purchased any Gmails yet.\n\n"
                "Click '🛒 Buy Gmails' to get started!"
            )
            return
        
        message = f"📦 **My Purchases** ({len(purchases)} total)\n\n"
        
        for gmail in purchases[:10]:  # Show last 10
            message += f"📧 `{gmail['email']}`\n"
        
        if len(purchases) > 10:
            message += f"\n...and {len(purchases) - 10} more\n"
        
        message += "\n💡 Tip: Scroll up to see all your credentials!"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def handle_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle custom quantity input"""
        query = update.callback_query
        await query.answer()
        
        context.user_data['awaiting_quantity'] = True
        
        await query.edit_message_text(
            f"✏️ **Custom Quantity**\n\n"
            f"Enter the number of Gmails you want to buy\n"
            f"(Minimum: {config.MIN_BUY_QUANTITY})"
        )
    
    @staticmethod
    async def process_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process custom quantity input"""
        if not context.user_data.get('awaiting_quantity'):
            return
        
        try:
            quantity = int(update.message.text.strip())
            context.user_data.pop('awaiting_quantity')
            
            # Use the quantity selection handler
            # Create a fake callback query update
            from telegram import CallbackQuery
            fake_query = type('obj', (object,), {
                'answer': lambda: None,
                'edit_message_text': update.message.reply_text
            })()
            
            fake_update = type('obj', (object,), {
                'callback_query': fake_query,
                'effective_user': update.effective_user
            })()
            
            await BuyerHandler.handle_quantity_selection(fake_update, context, quantity)
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid quantity. Please enter a valid number."
            )

buyer_handler = BuyerHandler()
