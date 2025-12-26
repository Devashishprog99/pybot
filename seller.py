"""
Seller Module - Handle seller operations
"""
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from utils import (
    parse_gmail_list, generate_batch_id, format_currency,
    build_seller_wizard_keyboard, build_withdrawal_keyboard
)
import config
import os

class SellerHandler:
    
    @staticmethod
    async def check_seller_status(user_id: int) -> dict:
        """Check if user is registered as seller"""
        seller = db.get_seller(user_id)
        return seller if seller else None
    
    @staticmethod
    async def start_selling(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start selling process"""
        user_id = update.effective_user.id
        
        # Check if already a seller
        seller = await SellerHandler.check_seller_status(user_id)
        
        if seller:
            if seller['status'] == 'pending':
                await update.message.reply_text(
                    "⏳ Your seller application is pending admin approval.\n"
                    "Please wait for approval before submitting Gmails."
                )
                return
            elif seller['status'] == 'approved':
                # Go to Gmail submission
                context.user_data['seller_step'] = 2
                await update.message.reply_text(
                    "📧 **Submit Your Gmail Accounts**\n\n"
                    "⚠️ **IMPORTANT REQUIREMENTS:**\n"
                    "**• GMAILS MUST NOT HAVE PHONE NUMBER ADDED**\n"
                    "**• MUST NOT HAVE 2-STEP VERIFICATION**\n"
                    "**• MUST NOT HAVE ANY RECOVERY EMAIL/PHONE**\n"
                    "**• MUST BE FRESH AND CLEAN ACCOUNTS ONLY**\n\n"
                    f"Format: `email:password` (one per line)\n"
                    f"Minimum: {config.MIN_SELL_QUANTITY} Gmails\n"
                    f"Rate: {format_currency(config.SELL_RATE)} per Gmail\n\n"
                    "Send your Gmail list now:",
                    parse_mode='Markdown'
                )
                return
        
        # Start new seller registration
        context.user_data['seller_step'] = 1
        await update.message.reply_text(
            "💰 **Become a Seller!**\n\n"
            f"Earn {format_currency(config.SELL_RATE)} per Gmail account\n"
            f"Minimum: {config.MIN_SELL_QUANTITY} Gmails\n\n"
            "**Step 1/3:** Upload your UPI QR code\n"
            "This will be used to pay you for your sales.\n\n"
            "📸 Send the QR code image now:",
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def handle_upi_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle UPI QR code upload"""
        user_id = update.effective_user.id
        
        if not update.message.photo:
            await update.message.reply_text("❌ Please send a valid QR code image.")
            return
        
        # Download and save QR code
        photo = update.message.photo[-1]  # Get highest resolution
        file = await context.bot.get_file(photo.file_id)
        
        # Create directory if not exists
        os.makedirs('upi_qrs', exist_ok=True)
        file_path = f"upi_qrs/seller_{user_id}_{photo.file_id}.jpg"
        await file.download_to_drive(file_path)
        
        # Save to context
        context.user_data['upi_qr_path'] = file_path
        context.user_data['seller_step'] = 2
        
        await update.message.reply_text(
            "✅ UPI QR code saved!\n\n"
            "**Step 2/3:** Submit Your Gmail Accounts\n\n"
            "⚠️ **IMPORTANT REQUIREMENTS:**\n"
            "**• GMAILS MUST NOT HAVE PHONE NUMBER ADDED**\n"
            "**• MUST NOT HAVE 2-STEP VERIFICATION**\n"
            "**• MUST NOT HAVE ANY RECOVERY EMAIL/PHONE**\n"
            "**• MUST BE FRESH AND CLEAN ACCOUNTS ONLY**\n\n"
            f"Format: `email:password` (one per line)\n"
            f"Minimum: {config.MIN_SELL_QUANTITY} Gmails\n"
            f"Rate: {format_currency(config.SELL_RATE)} per Gmail\n\n"
            "Example:\n"
            "`example1@gmail.com:password123`\n"
            "`example2@gmail.com:password456`\n\n"
            "Send your Gmail list now:",
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def handle_gmail_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Gmail list submission"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Parse Gmail list
        gmails = parse_gmail_list(text)
        
        if len(gmails) < config.MIN_SELL_QUANTITY:
            await update.message.reply_text(
                f"❌ Minimum {config.MIN_SELL_QUANTITY} Gmails required.\n"
                f"You submitted {len(gmails)} valid Gmail(s).\n\n"
                "Please check the format and try again."
            )
            return
        
        # Save to context
        context.user_data['gmails'] = gmails
        context.user_data['seller_step'] = 3
        
        # Calculate earnings
        total_earnings = len(gmails) * config.SELL_RATE
        
        await update.message.reply_text(
            "**Step 3/3:** Review Your Submission\n\n"
            f"📧 **Gmail Accounts:** {len(gmails)}\n"
            f"💰 **Potential Earnings:** {format_currency(total_earnings)}\n\n"
            "✅ Click Submit to send for admin approval.",
            reply_markup=build_seller_wizard_keyboard(3),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def submit_for_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Submit seller application for approval"""
        user_id = update.effective_user.id
        query = update.callback_query
        await query.answer()
        
        upi_qr_path = context.user_data.get('upi_qr_path')
        gmails = context.user_data.get('gmails')
        
        if not upi_qr_path or not gmails:
            await query.edit_message_text("❌ Error: Missing information. Please start again.")
            return
        
        # Check if already a seller
        seller = db.get_seller(user_id)
        
        if not seller:
            # Create seller account
            success = db.create_seller(user_id, upi_qr_path)
            if not success:
                await query.edit_message_text("❌ Error creating seller account. Please try again.")
                return
            seller = db.get_seller(user_id)
        
        # Validate Gmail credentials
        from utils import check_gmail_credentials
        await query.edit_message_text("🔍 **Validating credentials...**\n\nPlease wait...")
        
        valid_gmails = []
        invalid_count = 0
        
        for email, password in gmails:
            if check_gmail_credentials(email, password):
                valid_gmails.append((email, password))
            else:
                invalid_count += 1
        
        # Check if we have any valid accounts
        if not valid_gmails:
            await query.edit_message_text(
                "❌ **Validation Failed!**\n\n"
                f"⚠️ All {len(gmails)} accounts have invalid credentials.\n\n"
                "Please ensure:\n"
                "• Email and password are correct\n"
                "• Less secure app access is enabled\n"
                "• Accounts are not locked\n\n"
                "Try again with valid accounts.",
                parse_mode='Markdown'
            )
            return
        
        # Add valid Gmails to database
        batch_id = generate_batch_id()
        success = db.add_gmails(seller['seller_id'], valid_gmails, batch_id)
        
        if success:
            validation_msg = f"\n\n✅ Valid: {len(valid_gmails)}"
            if invalid_count > 0:
                validation_msg += f"\n❌ Invalid: {invalid_count} (rejected)"
            
            await query.edit_message_text(
                "✅ **Submission Successful!**\n\n"
                f"📧 {len(valid_gmails)} Gmails submitted for approval\n"
                f"🆔 Batch ID: `{batch_id}`\n"
                f"{validation_msg}\n\n"
                "⏳ Your submission is pending admin approval.\n"
                "You'll be notified once approved!",
                parse_mode='Markdown'
            )
            
            # Clear context
            context.user_data.clear()
            
            # Notify admins
            await SellerHandler.notify_admins_new_submission(context, user_id, len(valid_gmails), batch_id)
        else:
            await query.edit_message_text("❌ Error submitting Gmails. Please try again.")
    
    @staticmethod
    async def notify_admins_new_submission(context: ContextTypes.DEFAULT_TYPE, 
                                          user_id: int, count: int, batch_id: str):
        """Notify admins of new seller submission"""
        user = db.get_user(user_id)
        username = user.get('username', str(user_id)) if user else str(user_id)
        
        message = (
            f"🔔 **New Seller Submission**\n\n"
            f"👤 User: @{username} (ID: {user_id})\n"
            f"📧 Gmails: {count}\n"
            f"🆔 Batch: `{batch_id}`\n\n"
            f"Review in Admin Panel ⚙️"
        )
        
        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, message, parse_mode='Markdown')
            except:
                pass
    
    @staticmethod
    async def show_sales_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show seller sales statistics"""
        user_id = update.effective_user.id
        
        seller = db.get_seller(user_id)
        if not seller:
            await update.callback_query.edit_message_text(
                "❌ You're not registered as a seller yet.\n"
                "Click '📤 Sell Gmails' to get started!"
            )
            return
        
        stats = db.get_seller_sales(seller['seller_id'])
        
        message = (
            "📊 **My Sales Statistics**\n\n"
            f"✅ Sold: {stats.get('sold_count', 0)} Gmails\n"
            f"📦 Available: {stats.get('available_count', 0)} Gmails\n"
            f"⏳ Pending: {stats.get('pending_count', 0)} Gmails\n\n"
            f"💰 **Total Earnings:** {format_currency(seller['total_earnings'])}\n"
        )
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=build_withdrawal_keyboard(),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle withdrawal request"""
        user_id = update.effective_user.id
        query = update.callback_query
        await query.answer()
        
        seller = db.get_seller(user_id)
        if not seller or seller['total_earnings'] <= 0:
            await query.edit_message_text("❌ No earnings available for withdrawal.")
            return
        
        context.user_data['withdrawal_step'] = 1
        await query.edit_message_text(
            f"💰 **Withdrawal Request**\n\n"
            f"Available: {format_currency(seller['total_earnings'])}\n\n"
            "📸 Upload your UPI QR code to receive payment:"
        )
    
    @staticmethod
    async def submit_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Submit withdrawal request"""
        user_id = update.effective_user.id
        
        if not update.message.photo:
            await update.message.reply_text("❌ Please send a valid QR code image.")
            return
        
        seller = db.get_seller(user_id)
        if not seller:
            return
        
        # Download QR code
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_path = f"upi_qrs/withdrawal_{user_id}_{photo.file_id}.jpg"
        await file.download_to_drive(file_path)
        
        # Create withdrawal request
        withdrawal_id = db.create_withdrawal(
            seller['seller_id'],
            user_id,
            seller['total_earnings'],
            file_path
        )
        
        if withdrawal_id:
            await update.message.reply_text(
                "✅ **Withdrawal Request Submitted!**\n\n"
                f"Amount: {format_currency(seller['total_earnings'])}\n\n"
                "⏳ Your request is pending admin approval.\n"
                "Payment will be processed via UPI soon!"
            )
            
            # Notify admins
            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🔔 **New Withdrawal Request**\n\n"
                        f"👤 Seller: {seller['user_id']}\n"
                        f"💰 Amount: {format_currency(seller['total_earnings'])}\n"
                        f"Review in Admin Panel ⚙️",
                        parse_mode='Markdown'
                    )
                except:
                    pass
        else:
            await update.message.reply_text("❌ Error submitting withdrawal request.")

seller_handler = SellerHandler()
