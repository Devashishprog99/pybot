# Gmail Marketplace Telegram Bot

A Telegram bot for buying and selling Gmail accounts with integrated wallet system, Cashfree payment gateway, and admin approval workflow.

## Features

### For Buyers
- 🛒 Buy Gmail accounts (min 5 @ ₹15 each)
- 💰 Secure wallet system with Cashfree integration
- 📦 Instant credential delivery
- 📊 Purchase history tracking

### For Sellers
- 💵 Sell Gmail accounts (min 10 @ ₹8 each)
- 📸 UPI QR code integration for payments
- ⏳ Admin approval process
- 💰 Easy withdrawal system

### For Admins
- ⚙️ Complete admin panel
- ✅ Approve/reject sellers and listings
- 💳 Process withdrawal requests
- 📊 System statistics dashboard

## Installation

### 1. Clone or Download
```bash
cd "e:\bots tg\gmail-marketplace-bot"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your credentials:

```bash
copy .env.example .env
```

Edit `.env` with your details:
- **TELEGRAM_BOT_TOKEN**: Get from [@BotFather](https://t.me/BotFather)
- **ADMIN_IDS**: Your Telegram user ID (comma-separated for multiple admins)
- **CASHFREE_APP_ID**: From Cashfree dashboard
- **CASHFREE_SECRET_KEY**: From Cashfree dashboard
- **CASHFREE_ENV**: Set to `TEST` for testing, `PRODUCTION` for live

### 4. Run the Bot
```bash
python bot.py
```

## Project Structure

```
gmail-marketplace-bot/
├── bot.py              # Main application
├── config.py           # Configuration management
├── database.py         # Database operations
├── utils.py            # Utility functions and keyboards
├── payment.py          # Cashfree integration
├── seller.py           # Seller module
├── buyer.py            # Buyer module
├── admin.py            # Admin panel
├── schema.sql          # Database schema
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
└── README.md           # This file
```

## Usage

### Getting Your Telegram User ID
1. Start a chat with [@userinfobot](https://t.me/userinfobot)
2. It will reply with your user ID
3. Add this ID to `ADMIN_IDS` in `.env`

### Setting Up Cashfree
1. Sign up at [Cashfree](https://www.cashfree.com/)
2. Get your App ID and Secret Key from the dashboard
3. Start with TEST environment
4. Add your credentials to `.env`

### Bot Commands
The bot uses a button-based interface. After `/start`:
- 💰 **Wallet** - Add money and view balance
- 🛒 **Buy Gmails** - Purchase accounts
- 📤 **Sell Gmails** - Register as seller and submit accounts
- 📊 **My Activity** - View purchases, sales, withdrawals
- ⚙️ **Admin Panel** - Admin-only features

## Database

Uses SQLite by default. The database file (`gmail_marketplace.db`) is created automatically on first run.

### Tables
- **users** - User accounts and wallet balances
- **sellers** - Seller registrations
- **gmails** - Gmail account listings
- **transactions** - Payment transactions
- **withdrawals** - Withdrawal requests

## Payment Flow

1. User selects amount (₹15-₹500)
2. Cashfree order created with 5-minute expiry
3. User clicks payment link
4. Bot monitors payment status
5. On success, wallet credited automatically

## Admin Workflow

### Approving Sellers
1. Admin clicks **⚙️ Admin Panel**
2. Select **📋 Sellers**
3. Review seller info and UPI QR
4. Click **✅ Approve** or **❌ Reject**

### Approving Gmail Listings
1. Go to **Admin Panel** → **📧 Gmails**
2. Review batch details and sample emails
3. **✅ Approve All** or **❌ Reject All**

### Processing Withdrawals
1. Go to **Admin Panel** → **💰 Withdrawals**
2. Review seller earnings and UPI QR
3. Make manual UPI payment to seller
4. Click **✅ Mark as Paid**

## Security Notes

⚠️ **Important:**
- Keep your `.env` file secure and never commit it
- Use TEST environment first
- Selling Gmail accounts may violate Google's ToS
- Ensure legal compliance in your jurisdiction

## Troubleshooting

### Bot won't start
- Check `.env` file exists and has all required fields
- Verify TELEGRAM_BOT_TOKEN is correct
- Ensure ADMIN_IDS is a valid number

### Payment not working
- Verify Cashfree credentials
- Check CASHFREE_ENV is set correctly
- Ensure you're using TEST mode for testing

### Database errors
- Delete `gmail_marketplace.db` to reset
- Check write permissions in directory

## Support

For issues or questions:
1. Check the logs in console output
2. Verify your configuration
3. Test in small increments

## License

This project is for educational purposes. Use responsibly and ensure compliance with all applicable laws and terms of service.

---

Made with ❤️ for e-commerce automation
