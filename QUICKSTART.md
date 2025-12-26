# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Create Your Bot (2 min)
1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Choose a name: `Gmail Marketplace`
4. Choose a username: `YourGmailMarketBot` (must be unique)
5. **Copy the token** you receive (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Step 2: Get Your User ID (1 min)
1. Message [@userinfobot](https://t.me/userinfobot)
2. **Copy your user ID** (a number like: `123456789`)

### Step 3: Configure the Bot (1 min)
1. Open `e:\bots tg\gmail-marketplace-bot\.env.example`
2. Copy it as `.env` in the same folder
3. Edit `.env` and replace:
   ```env
   TELEGRAM_BOT_TOKEN=paste_your_bot_token_here
   ADMIN_IDS=paste_your_user_id_here
   ```

### Step 4: Set Up Cashfree (1 min)
1. For testing, you can use dummy credentials temporarily:
   ```env
   CASHFREE_APP_ID=TEST123
   CASHFREE_SECRET_KEY=TEST456
   CASHFREE_ENV=TEST
   ```
2. For production, sign up at [cashfree.com](https://www.cashfree.com) and get real credentials

### Step 5: Run! (30 sec)
```bash
cd "e:\bots tg\gmail-marketplace-bot"
python bot.py
```

You should see:
```
🚀 Bot is running...
📊 Environment: TEST
👥 Admin IDs: [your_id]
```

---

## ✅ First Test

1. Open Telegram
2. Search for your bot username
3. Send `/start`
4. You should see the welcome message with buttons!

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'telegram'"
```bash
pip install -r requirements.txt
```

### "Configuration errors: TELEGRAM_BOT_TOKEN is required"
- Make sure you created `.env` file (not `.env.example`)
- Check that the token is pasted correctly without quotes

### "Database error"
- Delete `gmail_marketplace.db` if it exists
- Restart the bot

### Bot doesn't respond
- Check that bot is running in terminal
- Verify token is correct in `.env`
- Make sure you're messaging the right bot

---

## 📝 Next Steps

1. **Test in TEST mode first** - Don't use real payment credentials yet
2. **Get real Cashfree credentials** when ready to accept payments
3. **Customize pricing** in `.env` file:
   ```env
   SELL_RATE=8
   BUY_RATE=15
   MIN_SELL_QUANTITY=10
   MIN_BUY_QUANTITY=5
   ```

---

## 📚 Full Documentation

See [README.md](file:///e:/bots%20tg/gmail-marketplace-bot/README.md) for complete setup and usage guide.
