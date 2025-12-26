"""
Admin Module - Admin panel and operations
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from mongodb import db
from utils import (
    build_admin_keyboard, build_approval_keyboard, 
    build_admin_nav_keyboard, format_currency, format_datetime,
    build_user_action_keyboard
)
import config

class AdminHandler:
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in config.ADMIN_IDS
    
    @staticmethod
    async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin panel"""
        user_id = update.effective_user.id
        
        if not AdminHandler.is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer("❌ Unauthorized access!", show_alert=True)
            else:
                await update.message.reply_text("❌ You don't have admin access!")
            return
        
        message = "⚙️ **Admin Panel**\n\nSelect an option:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=build_admin_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=build_admin_keyboard(),
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin dashboard with statistics"""
        query = update.callback_query
        await query.answer()
        
        stats = db.get_stats()
        
        message = (
            "📊 **Admin Dashboard**\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"📧 Available Gmails: {stats['available_gmails']}\n"
            f"✅ Sold Gmails: {stats['sold_gmails']}\n\n"
            f"**Pending Approvals:**\n"
            f"👨‍💼 Sellers: {stats['pending_sellers']}\n"
            f"📦 Gmail Batches: {stats['pending_batches']}\n"
            f"💰 Withdrawals: {stats['pending_withdrawals']}\n\n"
            f"💵 Total Revenue: {format_currency(stats['total_revenue'])}"
        )
        
        keyboard = [[]]
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def show_pending_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all sellers with statistics"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Get all sellers with their stats
            sellers_stats = db.get_all_sellers_with_stats()
            
            if not sellers_stats or len(sellers_stats) == 0:
                await query.edit_message_text(
                    "📋 **No sellers registered yet!**\n\n"
                    "Sellers will appear here once users register to sell Gmails.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]]),
                    parse_mode='Markdown'
                )
                return
            
            # Format seller statistics
            message = "📋 **All Sellers Statistics**\n\n"
            
            for seller in sellers_stats:
                status_emoji = "⏳" if seller['status'] == 'pending' else "✅" if seller['status'] == 'approved' else "❌"
                username = seller.get('username', 'Unknown')
                user_id = seller.get('user_id', 0)
                pending = seller.get('pending_gmails', 0)
                available = seller.get('available_gmails', 0)
                sold = seller.get('sold_gmails', 0)
                earnings = seller.get('total_earnings', 0.0)
                
                message += f"{status_emoji} **{username}** (ID: {user_id})\n"
                message += f"   📊 Pending: {pending} | Available: {available} | Sold: {sold}\n"
                message += f"   💰 Earnings: {format_currency(earnings)}\n\n"
            
            keyboard = [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error in show_pending_sellers: {e}")
            await query.edit_message_text(
                f"❌ Error loading sellers: {str(e)}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]])
            )
    
    @staticmethod
    async def display_seller_for_approval(query, seller, index, total):
        """Display seller details for approval"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        message = (
            f"👨‍💼 **Seller Approval** ({index + 1}/{total})\n\n"
            f"👤 User: {seller['username']}\n"
            f"🆔 User ID: {seller['user_id']}\n"
            f"📅 Registered: {format_datetime(seller['created_at'])}\n\n"
            "📸 UPI QR Code attached below"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_seller_{seller['seller_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_seller_{seller['seller_id']}")
            ]
        ]
        
        if index > 0:
            keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data="seller_prev")])
        if index < total - 1:
            keyboard[len(keyboard)-1].append(InlineKeyboardButton("Next ➡️", callback_data="seller_next"))
        
        keyboard.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="admin_panel")])
        
        # Send UPI QR
        try:
            await query.message.reply_photo(
                photo=open(seller['upi_qr_path'], 'rb'),
                caption=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            # Delete old message
            await query.message.delete()
        except:
            await query.edit_message_text(
                message + "\n\n⚠️ QR Code not found",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def approve_seller(update: Update, context: ContextTypes.DEFAULT_TYPE, seller_id: int):
        """Approve seller"""
        query = update.callback_query
        await query.answer("✅ Seller approved!")
        
        admin_id = update.effective_user.id
        db.approve_seller(seller_id, admin_id, approved=True)
        
        # Get seller info and notify
        seller = db.get_seller_by_id(seller_id) if hasattr(db, 'get_seller_by_id') else None
        
        await query.edit_message_caption(
            caption="✅ **Seller Approved!**\n\nUser has been notified.",
            parse_mode='Markdown'
        )
        
        # Move to next seller or return to list
        await AdminHandler.show_pending_sellers(update, context)
    
    @staticmethod
    async def reject_seller(update: Update, context: ContextTypes.DEFAULT_TYPE, seller_id: int):
        """Reject seller"""
        query = update.callback_query
        await query.answer("❌ Seller rejected!")
        
        admin_id = update.effective_user.id
        db.approve_seller(seller_id, admin_id, approved=False)
        
        await query.edit_message_caption(
            caption="❌ **Seller Rejected!**\n\nUser has been notified.",
            parse_mode='Markdown'
        )
        
        await AdminHandler.show_pending_sellers(update, context)
    
    @staticmethod
    async def show_pending_gmails(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending Gmail batch approvals"""
        query = update.callback_query
        await query.answer()
        
        try:
            batches = db.get_pending_gmail_batches()
            
            if not batches or len(batches) == 0:
                await query.edit_message_text(
                    "📧 **No pending Gmail batches!**\n\n"
                    "Gmail batches will appear here when sellers submit accounts for approval.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]]),
                    parse_mode='Markdown'
                )
                return
            
            context.user_data['pending_batches'] = batches
            context.user_data['batch_index'] = 0
            
            await AdminHandler.display_batch_for_approval(query, batches[0], 0, len(batches))
        except Exception as e:
            print(f"Error in show_pending_gmails: {e}")
            await query.edit_message_text(
                f"❌ Error loading Gmail batches: {str(e)}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]])
            )
    
    @staticmethod
    async def display_batch_for_approval(query, batch, index, total):
        """Display Gmail batch for approval"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Get sample emails (first 3)
        sample = batch['sample_emails'].split(', ')[:3]
        sample_text = '\n'.join([f"• `{email}`" for email in sample])
        
        message = (
            f"📧 **Gmail Batch Approval** ({index + 1}/{total})\n\n"
            f"👤 Seller: {batch['username']}\n"
            f"📊 Count: {batch['count']} Gmails\n"
            f"📅 Submitted: {format_datetime(batch['created_at'])}\n\n"
            f"**Sample Emails:**\n{sample_text}\n"
            f"{'...' if batch['count'] > 3 else ''}\n\n"
            f"🆔 Batch ID: `{batch['batch_id']}`"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve All", callback_data=f"approve_batch_{batch['batch_id']}"),
                InlineKeyboardButton("❌ Reject All", callback_data=f"reject_batch_{batch['batch_id']}")
            ]
        ]
        
        if index > 0:
            keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data="batch_prev")])
        if index < total - 1:
            if len(keyboard[-1]) == 1:
                keyboard[-1].append(InlineKeyboardButton("Next ➡️", callback_data="batch_next"))
            else:
                keyboard.append([InlineKeyboardButton("Next ➡️", callback_data="batch_next")])
        
        keyboard.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="admin_panel")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def approve_gmail_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, batch_id: str):
        """Approve Gmail batch"""
        query = update.callback_query
        await query.answer("✅ Batch approved!")
        
        db.approve_gmail_batch(batch_id, approved=True)
        
        await query.edit_message_text(
            f"✅ **Batch Approved!**\n\nGmails are now available for purchase.\n\n🆔 `{batch_id}`",
            parse_mode='Markdown'
        )
        
        await AdminHandler.show_pending_gmails(update, context)
    
    @staticmethod
    async def reject_gmail_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, batch_id: str):
        """Reject Gmail batch"""
        query = update.callback_query
        await query.answer("❌ Batch rejected!")
        
        db.approve_gmail_batch(batch_id, approved=False)
        
        await query.edit_message_text(
            f"❌ **Batch Rejected!**\n\nSeller has been notified.\n\n🆔 `{batch_id}`",
            parse_mode='Markdown'
        )
        
        await AdminHandler.show_pending_gmails(update, context)
    
    @staticmethod
    async def show_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending withdrawal requests - only sellers with actual sales"""
        query = update.callback_query
        await query.answer()
        
        # Get withdrawals only from sellers who have sold Gmails
        withdrawals = db.get_pending_withdrawals_with_sales()
        
        if not withdrawals:
            await query.edit_message_text(
                "✅ No pending withdrawal requests from sellers with sales!",
                reply_markup=build_admin_nav_keyboard('withdrawals')
            )
            return
        
        context.user_data['pending_withdrawals'] = withdrawals
        context.user_data['withdrawal_index'] = 0
        
        await AdminHandler.display_withdrawal_for_approval(query, withdrawals[0], 0, len(withdrawals))
    
    @staticmethod
    async def display_withdrawal_for_approval(query, withdrawal, index, total):
        """Display withdrawal request for approval"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        message = (
            f"💰 **Withdrawal Request** ({index + 1}/{total})\n\n"
            f"👤 Seller: {withdrawal['username']}\n"
            f"🆔 User ID: {withdrawal['user_id']}\n"
            f"💵 Amount: {format_currency(withdrawal['amount'])}\n"
            f"📊 Total Earnings: {format_currency(withdrawal['total_earnings'])}\n"
            f"📅 Requested: {format_datetime(withdrawal['created_at'])}\n\n"
            "📸 UPI QR Code attached below"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Mark as Paid", callback_data=f"approve_withdrawal_{withdrawal['withdrawal_id']}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"reject_withdrawal_{withdrawal['withdrawal_id']}")
            ]
        ]
        
        if index > 0:
            keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data="withdrawal_prev")])
        if index < total - 1:
            if len(keyboard[-1]) == 1:
                keyboard[-1].append(InlineKeyboardButton("Next ➡️", callback_data="withdrawal_next"))
            else:
                keyboard.append([InlineKeyboardButton("Next ➡️", callback_data="withdrawal_next")])
        
        keyboard.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="admin_panel")])
        
        # Send with QR code
        try:
            await query.message.reply_photo(
                photo=open(withdrawal['upi_qr_path'], 'rb'),
                caption=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            await query.message.delete()
        except:
            await query.edit_message_text(
                message + "\n\n⚠️ QR Code not found",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE, withdrawal_id: int):
        """Approve withdrawal and mark as paid"""
        query = update.callback_query
        await query.answer("✅ Marked as paid!")
        
        admin_id = update.effective_user.id
        db.process_withdrawal(withdrawal_id, admin_id, approved=True)
        
        await query.edit_message_caption(
            caption="✅ **Payment Processed!**\n\nSeller has been notified.",
            parse_mode='Markdown'
        )
        
        await AdminHandler.show_pending_withdrawals(update, context)
    
    @staticmethod
    async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE, withdrawal_id: int):
        """Reject withdrawal request"""
        query = update.callback_query
        await query.answer("❌ Withdrawal declined!")
        
        admin_id = update.effective_user.id
        db.process_withdrawal(withdrawal_id, admin_id, approved=False)
        
        await query.edit_message_caption(
            caption="❌ **Withdrawal Declined!**\n\nSeller has been notified.",
            parse_mode='Markdown'
        )
        
        await AdminHandler.show_pending_withdrawals(update, context)

admin_handler = AdminHandler()
