# 🤖 Virtual Number Selling Bot

Telegram bot for selling international virtual numbers with UPI + USDT payments.

## Features

### User Side
- Browse countries with prices
- Pay via UPI or USDT
- Upload payment screenshot
- Real-time order tracking
- `/myorders` — order history

### Admin Side
- Instant notification for every order (with payment proof)
- One-click Approve / Reject
- Send number directly after approval
- `/orders` — view all pending orders
- `/stats` — revenue & stats
- `/skip` — cancel pending number delivery

---

## Railway Deployment

### Step 1 — Create Bot
1. Message `@BotFather` on Telegram
2. `/newbot` → get your `BOT_TOKEN`
3. Get your Telegram ID from `@userinfobot`

### Step 2 — Railway Setup
1. Push this code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add a **PostgreSQL** plugin to your project
4. Copy `DATABASE_URL` from PostgreSQL plugin

### Step 3 — Environment Variables
Add these in Railway → Variables:

```
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_id
DATABASE_URL=postgresql://...  (auto-filled by Railway PostgreSQL)
UPI_ID=yourname@upi
USDT_ADDRESS=TYourTRC20Address
USDT_NETWORK=TRC20
SUPPORT_USERNAME=YourTelegramUsername
```

### Step 4 — Deploy
- Railway auto-detects `Procfile` and runs `python main.py`
- Check logs to confirm: `✅ Database initialized` + `🤖 Bot running...`

---

## Order Flow

```
User /start
  → Browse Countries
    → Select Country (e.g. 🇩🇪 Germany ₹99)
      → Select Payment (UPI / USDT)
        → Payment Details shown
          → "I've Paid" → Send Screenshot
            → Admin gets notification + proof photo
              → Admin clicks ✅ Approve
                → Admin sends the number (just type it)
                  → User receives number instantly
```

---

## Admin Commands

| Command | Description |
|---------|-------------|
| `/orders` | View all pending orders |
| `/stats` | Revenue & user statistics |
| `/skip` | Cancel current number delivery |

---

## Database Tables

**users** — `user_id, username, first_name, created_at`

**orders** — `id, user_id, country_key, country_name, price, payment_method, status, proof_file_id, number_delivered, created_at, updated_at`

**Order Statuses:** `pending → approved → delivered` or `rejected`
