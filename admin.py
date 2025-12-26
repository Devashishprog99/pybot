"""
Admin Module - Admin panel and operations
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
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
                # Escape underscores for Markdown
                if username != 'Unknown':
                    username = username.replace('_', '\\_')
                    
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
        """Show Gmail overview - list sellers with Gmail counts"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Get all sellers with their Gmail stats
            sellers = db.get_all_sellers_with_stats()
            
            if not sellers or len(sellers) == 0:
                await query.edit_message_text(
                    "📧 **Gmail Overview**\n\n"
                    "No sellers with Gmails yet.\n"
                    "Gmails will appear here when sellers submit accounts.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]]),
                    parse_mode='Markdown'
                )
                return
            
            # Build seller list with pagination
            page = context.user_data.get('gmail_page', 0)
            per_page = 8
            total_pages = (len(sellers) + per_page - 1) // per_page
            start = page * per_page
            end = min(start + per_page, len(sellers))
            
            message = f"📧 **Gmail Overview** (Page {page + 1}/{total_pages})\n\n"
            message += "Select a seller to view their Gmails:\n\n"
            
            keyboard = []
            for seller in sellers[start:end]:
                username = seller.get('username', 'Unknown')
                if username and username != 'Unknown':
                    username = username.replace('_', '\\_')
                pending = seller.get('pending_gmails', 0)
                available = seller.get('available_gmails', 0)
                sold = seller.get('sold_gmails', 0)
                
                btn_text = f"👤 {username} - P:{pending} A:{available} S:{sold}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"seller_gmails_{seller['user_id']}")])
            
            # Pagination buttons
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data="gmail_page_prev"))
            if page < total_pages - 1:
                nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="gmail_page_next"))
            if nav_row:
                keyboard.append(nav_row)
            
            # Pending batches button
            keyboard.append([InlineKeyboardButton("📋 Pending Batches", callback_data="pending_batches")])
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")])
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error in show_pending_gmails: {e}")
            await query.edit_message_text(
                f"❌ Error loading Gmails: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]])
            )
    
    @staticmethod
    async def show_seller_gmails(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show specific seller's Gmail details"""
        query = update.callback_query
        await query.answer()
        
        try:
            seller = db.get_seller(user_id)
            user = db.get_user(user_id)
            
            if not seller:
                await query.answer("Seller not found!", show_alert=True)
                return
            
            # Get Gmail batches for this seller
            batches = db.get_seller_gmail_batches(seller['seller_id'])
            
            username = user.get('username', 'Unknown') if user else 'Unknown'
            if username != 'Unknown':
                username = username.replace('_', '\\_')
            
            message = f"📧 **{username}'s Gmails**\n\n"
            
            if not batches:
                message += "No Gmail batches found."
            else:
                for batch in batches[:5]:  # Show max 5 batches
                    status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(batch['status'], "❓")
                    message += f"{status_emoji} Batch: `{batch['batch_id'][:15]}...`\n"
                    message += f"   Count: {batch['count']} | Status: {batch['status']}\n\n"
            
            # Get sold gmails info
            sold_gmails = db.get_sold_gmails_by_seller(seller['seller_id'])
            if sold_gmails:
                message += f"\n**Sold Gmails ({len(sold_gmails)}):**\n"
                for gmail in sold_gmails[:3]:
                    buyer_name = gmail.get('buyer_username', 'Unknown')
                    if buyer_name and buyer_name != 'Unknown':
                        buyer_name = buyer_name.replace('_', '\\_')
                    message += f"• `{gmail['email'][:20]}...` → {buyer_name}\n"
                if len(sold_gmails) > 3:
                    message += f"  ...and {len(sold_gmails) - 3} more\n"
            
            keyboard = [[InlineKeyboardButton("⬅️ Back to Gmails", callback_data="admin_gmails")]]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error showing seller gmails: {e}")
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gmails")]])
            )
    
    @staticmethod
    async def show_pending_batches(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending Gmail batch approvals"""
        query = update.callback_query
        await query.answer()
        
        try:
            batches = db.get_pending_gmail_batches()
            
            if not batches or len(batches) == 0:
                await query.edit_message_text(
                    "📋 **No pending Gmail batches!**\n\n"
                    "All batches have been processed.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gmails")]]),
                    parse_mode='Markdown'
                )
                return
            
            context.user_data['pending_batches'] = batches
            context.user_data['batch_index'] = 0
            
            await AdminHandler.display_batch_for_approval(query, batches[0], 0, len(batches))
        except Exception as e:
            print(f"Error in show_pending_batches: {e}")
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gmails")]])
            )

    
    @staticmethod
    async def display_batch_for_approval(query, batch, index, total):
        """Display Gmail batch for approval"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Get sample emails (first 3) and escape underscores
        sample = batch['sample_emails'].split(', ')[:3]
        escaped_sample = [email.replace('_', r'\_') for email in sample]
        sample_text = '\n'.join([f"• `{email}`" for email in escaped_sample])
        
        # Escape username underscores
        username = batch['username']
        if username:
            username = username.replace('_', r'\_')

        
        message = (
            f"📧 **Gmail Batch Approval** ({index + 1}/{total})\n\n"
            f"👤 Seller: {username}\n"
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
        
        # Escape username underscores
        username = withdrawal['username']
        if username:
            username = username.replace('_', '\\_')
        
        message = (
            f"💰 **Withdrawal Request** ({index + 1}/{total})\n\n"
            f"👤 Seller: {username}\n"
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

    @staticmethod
    async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all registered users"""
        query = update.callback_query
        await query.answer()
        
        users = db.get_all_users()
        
        if not users:
            await query.edit_message_text(
                "👥 **No users found!**",
                reply_markup=build_admin_nav_keyboard("users"),
                parse_mode='Markdown'
            )
            return
            
        message = f"👥 **Total Users: {len(users)}**\n\n"
        
        # Show last 15 users to avoid message length limits
        for user in users[:15]:
            status = "🚫 Banned" if user.get('is_banned') else "✅ Active"
            is_seller_data = db.get_seller(user['user_id'])
            is_seller = "💼 Seller" if is_seller_data else "👤 Buyer"
            
            # Escape underscores in username for Markdown
            username = user.get('username', 'No Username')
            if username != 'No Username':
                username = username.replace('_', '\\_')
            
            message += (
                f"👤 `{user['user_id']}` | {username}\n"
                f"💰 Balance: {format_currency(user.get('wallet_balance', 0))}\n"
                f"🎫 Status: {status} | {is_seller}\n\n"
            )
            
        if len(users) > 15:
            message += f"... and {len(users) - 15} more users.\n"
            
        message += "\nTo manage a specific user, forward their message or send User ID."
        
        await query.edit_message_text(
            message,
            reply_markup=build_admin_nav_keyboard("users"),
            parse_mode='Markdown'
        )

    @staticmethod
    async def manage_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Manage a specific user"""
        user = db.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ User not found.")
            return
            
        is_banned = user.get('is_banned', False)
        status = "🚫 BANNED" if is_banned else "✅ ACTIVE"
        
        message = (
            f"👤 **User Management**\n\n"
            f"ID: `{user['user_id']}`\n"
            f"Username: @{user.get('username', 'None')}\n"
            f"Name: {user.get('full_name', 'None')}\n"
            f"Balance: {format_currency(user.get('wallet_balance', 0))}\n"
            f"Status: {status}\n"
            f"Joined: {format_datetime(user.get('created_at'))}"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=build_user_action_keyboard(user_id, is_banned),
            parse_mode='Markdown'
        )

    @staticmethod
    async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, ban: bool):
        """Ban or unban a user"""
        query = update.callback_query
        await query.answer("Processing...")
        
        if db.ban_user(user_id, ban):
            action = "banned" if ban else "unbanned"
            await query.edit_message_text(
                text=f"✅ User `{user_id}` has been **{action}**.",
                parse_mode='Markdown',
                reply_markup=build_admin_nav_keyboard("users")
            )
        else:
            await query.answer("❌ Failed to update user status.")

    @staticmethod
    async def show_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show sellers awaiting payment for sold Gmails"""
        query = update.callback_query
        await query.answer()
        
        try:
            sellers_awaiting_payment = db.get_sellers_awaiting_payment()
            
            if not sellers_awaiting_payment:
                await query.edit_message_text(
                    "✅ **No pending payments!**\n\n"
                    "All sellers with sales have been paid.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]]),
                    parse_mode='Markdown'
                )
                return
            
            context.user_data['pending_payments'] = sellers_awaiting_payment
            context.user_data['payment_index'] = 0
            
            await AdminHandler.display_pending_payment(query, sellers_awaiting_payment[0], 0, len(sellers_awaiting_payment))
        except Exception as e:
            print(f"Error in show_pending_payments: {e}")
            await query.edit_message_text(
                f"❌ Error loading pending payments: {str(e)}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]])
            )
    
    @staticmethod
    async def display_pending_payment(query, payment_info, index, total):
        """Display seller payment info with UPI QR"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Escape username underscores
        username = payment_info.get('username', 'Unknown')
        if username and username != 'Unknown':
            username = username.replace('_', '\\_')
        
        message = (
            f"💸 **Pending Payment** ({index + 1}/{total})\n\n"
            f"👤 Seller: {username}\n"
            f"🆔 User ID: {payment_info['user_id']}\n"
            f"📧 Sold Gmails: {payment_info['sold_count']}\n"
            f"💰 Amount Owed: {format_currency(payment_info['amount_owed'])}\n"
            f"📅 Last Sale: {format_datetime(payment_info['last_sale_date'])}\n\n"
            "📸 UPI QR Code attached below\n\n"
            "**Options:**\n"
            "• Upload payment screenshot (recommended)\n"
            "• Or click 'Mark as Paid' directly"
        )
        
        keyboard = [
            [InlineKeyboardButton("📤 Upload Payment Proof", callback_data=f"upload_proof_{payment_info['user_id']}")],
            [InlineKeyboardButton("✅ Mark as Paid (No Proof)", callback_data=f"mark_paid_{payment_info['user_id']}")],
        ]
        
        # Pagination
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data="payment_prev"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="payment_next"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="admin_panel")])

        
        # Send with QR code
        try:
            upi_qr_path = payment_info.get('upi_qr_path')
            if upi_qr_path:
                await query.message.reply_photo(
                    photo=open(upi_qr_path, 'rb'),
                    caption=message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                await query.message.delete()
            else:
                await query.edit_message_text(
                    message + "\n\n⚠️ QR Code not found",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            print(f"Error showing QR: {e}")
            await query.edit_message_text(
                message + "\n\n⚠️ QR Code not found",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

admin_handler = AdminHandler()
