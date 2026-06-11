import os
import logging
import pg8000.native
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ['BOT_TOKEN']
ADMIN_ID     = int(os.environ['ADMIN_ID'])
DATABASE_URL = os.environ['DATABASE_URL']
UPI_ID       = os.environ.get('UPI_ID', 'yourname@upi')
USDT_ADDR    = os.environ.get('USDT_ADDRESS', 'TYourUSDTAddress')
USDT_NET     = os.environ.get('USDT_NETWORK', 'TRC20')
SUPPORT_USER = os.environ.get('SUPPORT_USERNAME', 'YourUsername')
BOT_NAME     = os.environ.get('BOT_NAME', 'NumBot Pro')

# ─── Services ────────────────────────────────────────────────────────────────
SERVICES = {
    'whatsapp':  {'name': 'WhatsApp',  'emoji': '📱', 'color': 'green'},
    'facebook':  {'name': 'Facebook',  'emoji': '📘', 'color': 'blue'},
    'tiktok':    {'name': 'TikTok',    'emoji': '🎵', 'color': 'black'},
    'telegram':  {'name': 'Telegram',  'emoji': '✈️', 'color': 'blue'},
    'gmail':     {'name': 'Gmail',     'emoji': '📧', 'color': 'red'},
    'instagram': {'name': 'Instagram', 'emoji': '📸', 'color': 'pink'},
    'imo':       {'name': 'IMO',       'emoji': '💬', 'color': 'blue'},
    'twitter':   {'name': 'Twitter/X', 'emoji': '🐦', 'color': 'blue'},
    'snapchat':  {'name': 'Snapchat',  'emoji': '👻', 'color': 'yellow'},
    'other':     {'name': 'Other',     'emoji': '🔢', 'color': 'gray'},
}

# ─── Countries ────────────────────────────────────────────────────────────────
COUNTRIES = {
    'iraq':          {'name': '🇮🇶 Iraq',           'price': 79},
    'fresh_iraq':    {'name': '🇮🇶 Fresh Iraq',      'price': 99},
    'new_iraq':      {'name': '🇮🇶 New Iraq',        'price': 99},
    'zambia':        {'name': '🇿🇲 Zambia',          'price': 79},
    'tunisia':       {'name': '🇹🇳 Tunisia',         'price': 79},
    'indonesia':     {'name': '🇮🇩 Indonesia',       'price': 79},
    'germany':       {'name': '🇩🇪 Germany',         'price': 99},
    'ghana':         {'name': '🇬🇭 Ghana',           'price': 79},
    'sudan':         {'name': '🇸🇩 Sudan',           'price': 79},
    'venezuela':     {'name': '🇻🇪 Venezuela N',     'price': 79},
    'saudi':         {'name': '🇸🇦 Saudi Arabia',    'price': 99},
    'fresh_russia':  {'name': '🇷🇺 Fresh Russia',    'price': 99},
    'new_russia':    {'name': '🇷🇺 New Russia',      'price': 99},
    'kyrgyzstan':    {'name': '🇰🇬 Kyrgyzstan',      'price': 99},
    'nigeria':       {'name': '🇳🇬 Nigeria',         'price': 79},
    'fresh_nigeria': {'name': '🇳🇬 Fresh Nigeria',   'price': 99},
    'new_nigeria':   {'name': '🇳🇬 New Nigeria',     'price': 99},
    'timor':         {'name': '🇹🇱 Timor-Leste',     'price': 79},
}

WAITING_PROOF = 1

# ─── Database ─────────────────────────────────────────────────────────────────
def get_db():
    r = urlparse(DATABASE_URL)
    params = dict(host=r.hostname, port=r.port or 5432,
                  database=r.path.lstrip('/'), user=r.username, password=r.password)
    if r.hostname and 'railway' in r.hostname:
        params['ssl_context'] = True
    return pg8000.native.Connection(**params)

def init_db():
    conn = get_db()
    conn.run("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT,
        created_at TIMESTAMP DEFAULT NOW())""")
    conn.run("""CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
        service TEXT, country_key TEXT, country_name TEXT,
        price INTEGER, payment_method TEXT, status TEXT DEFAULT 'pending',
        proof_file_id TEXT, number_delivered TEXT,
        created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())""")
    conn.close()
    logger.info("✅ DB ready")

def save_user(uid, uname, fname):
    conn = get_db()
    conn.run("""INSERT INTO users(user_id,username,first_name) VALUES(:u,:n,:f)
        ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,first_name=EXCLUDED.first_name""",
        u=uid, n=uname, f=fname)
    conn.close()

def create_order(uid, service, country_key, method, proof_fid):
    c = COUNTRIES[country_key]
    conn = get_db()
    rows = conn.run("""INSERT INTO orders(user_id,service,country_key,country_name,price,payment_method,proof_file_id)
        VALUES(:u,:sv,:ck,:cn,:p,:m,:pf) RETURNING id""",
        u=uid, sv=service, ck=country_key, cn=c['name'], p=c['price'], m=method, pf=proof_fid)
    oid = rows[0][0]
    conn.close()
    return oid

def get_order(oid):
    conn = get_db()
    rows = conn.run("SELECT * FROM orders WHERE id=:i", i=oid)
    cols = [c['name'] for c in conn.columns]
    conn.close()
    return dict(zip(cols, rows[0])) if rows else None

def update_order(oid, status, number=None):
    conn = get_db()
    if number:
        conn.run("UPDATE orders SET status=:s,number_delivered=:n,updated_at=NOW() WHERE id=:i",
                 s=status, n=number, i=oid)
    else:
        conn.run("UPDATE orders SET status=:s,updated_at=NOW() WHERE id=:i", s=status, i=oid)
    conn.close()

def get_user_orders(uid):
    conn = get_db()
    rows = conn.run("SELECT * FROM orders WHERE user_id=:u ORDER BY created_at DESC LIMIT 10", u=uid)
    cols = [c['name'] for c in conn.columns]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

def get_pending_orders():
    conn = get_db()
    rows = conn.run("SELECT * FROM orders WHERE status='pending' ORDER BY created_at DESC")
    cols = [c['name'] for c in conn.columns]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

def get_stats():
    conn = get_db()
    r1 = conn.run("SELECT COUNT(*),COALESCE(SUM(price),0) FROM orders WHERE status='delivered'")[0]
    r2 = conn.run("SELECT COUNT(*) FROM orders WHERE status='pending'")[0][0]
    r3 = conn.run("SELECT COUNT(*) FROM users")[0][0]
    conn.close()
    return r1[0], r1[1], r2, r3

def get_service_order_count(service):
    conn = get_db()
    r = conn.run("SELECT COUNT(*) FROM orders WHERE service=:s AND status='delivered'", s=service)
    conn.close()
    return r[0][0] if r else 0

# ─── Keyboards ────────────────────────────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buy Number", callback_data="buy")],
        [InlineKeyboardButton("📋 My Orders", callback_data="my_orders"),
         InlineKeyboardButton("💰 Price List", callback_data="prices")],
        [InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{SUPPORT_USER}")],
    ])

def services_kb():
    btns = []
    row = []
    for k, s in SERVICES.items():
        row.append(InlineKeyboardButton(f"{s['emoji']} {s['name']}", callback_data=f"svc_{k}"))
        if len(row) == 2:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(btns)

def countries_kb(service_key):
    btns = [[InlineKeyboardButton(
        f"{d['name']} — ₹{d['price']}", callback_data=f"ctry_{service_key}_{k}"
    )] for k, d in COUNTRIES.items()]
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="buy")])
    return InlineKeyboardMarkup(btns)

def payment_kb(svc, ctry):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 UPI / Bank", callback_data=f"pay_upi_{svc}_{ctry}")],
        [InlineKeyboardButton("💰 USDT Crypto", callback_data=f"pay_usdt_{svc}_{ctry}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"svc_{svc}")],
    ])

def paid_kb(method, svc, ctry):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid — Send Proof", callback_data=f"paid_{method}_{svc}_{ctry}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
    ])

def after_delivery_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Buy Another Number", callback_data="buy")],
        [InlineKeyboardButton("📞 Contact Support for OTP", url=f"https://t.me/{SUPPORT_USER}")],
        [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
    ])

def admin_kb(oid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{oid}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{oid}"),
    ]])

STATUS_EMOJI = {'pending':'⏳','approved':'🔄','delivered':'✅','rejected':'❌'}

# ─── Handlers ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"👋 *Welcome to {BOT_NAME}!*\n\n"
        "🌍 Premium International Virtual Numbers\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "✅ Works for WhatsApp, FB, TikTok & more\n"
        "✅ Fast Delivery | Trusted Seller\n"
        "✅ UPI & USDT Accepted\n"
        "✅ 18+ Countries Available\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Tap *Buy Number* to get started 👇",
        parse_mode='Markdown', reply_markup=main_menu_kb()
    )

async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        f"🏠 *{BOT_NAME} — Main Menu*\n\nWhat would you like to do?",
        parse_mode='Markdown', reply_markup=main_menu_kb()
    )

async def cb_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = "📱 *Select App / Service*\n\nWhich app do you need the number for?\n\n"
    for k, s in SERVICES.items():
        text += f"{s['emoji']} {s['name']}\n"
    await q.edit_message_text(text, parse_mode='Markdown', reply_markup=services_kb())

async def cb_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_key = q.data[4:]  # strip "svc_"
    if svc_key not in SERVICES:
        await q.answer("Invalid!", show_alert=True); return
    s = SERVICES[svc_key]
    await q.edit_message_text(
        f"{s['emoji']} *{s['name']} — Select Country*\n\n"
        "🔥 Fresh/New Numbers — ₹99\n"
        "✅ Standard Numbers — ₹79\n\n"
        "Choose your country:",
        parse_mode='Markdown', reply_markup=countries_kb(svc_key)
    )

async def cb_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    # format: ctry_whatsapp_iraq
    parts = q.data[5:].split('_', 1)  # strip "ctry_"
    svc_key, ctry_key = parts[0], parts[1]
    if ctry_key not in COUNTRIES or svc_key not in SERVICES:
        await q.answer("Invalid!", show_alert=True); return
    c = COUNTRIES[ctry_key]; s = SERVICES[svc_key]
    await q.edit_message_text(
        f"📦 *Order Summary*\n\n"
        f"App: {s['emoji']} *{s['name']}*\n"
        f"Country: *{c['name']}*\n"
        f"Price: *₹{c['price']}*\n\n"
        f"Select payment method 👇",
        parse_mode='Markdown', reply_markup=payment_kb(svc_key, ctry_key)
    )

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    # format: pay_upi_whatsapp_iraq
    parts = q.data.split('_', 3)
    method, svc_key, ctry_key = parts[1], parts[2], parts[3]
    if ctry_key not in COUNTRIES:
        await q.answer("Invalid!", show_alert=True); return
    c = COUNTRIES[ctry_key]; s = SERVICES[svc_key]
    if method == 'upi':
        text = (
            f"💳 *UPI Payment*\n\n"
            f"App: {s['emoji']} {s['name']}\n"
            f"Country: {c['name']}\n"
            f"Amount: *₹{c['price']}*\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"UPI ID: `{UPI_ID}`\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"1️⃣ Send ₹{c['price']} to above UPI\n"
            f"2️⃣ Take screenshot of payment\n"
            f"3️⃣ Click *I've Paid* & send screenshot\n\n"
            f"⚠️ Do NOT close this chat after paying!"
        )
    else:
        usdt = round(c['price'] / 85, 2)
        text = (
            f"💰 *USDT Payment ({USDT_NET})*\n\n"
            f"App: {s['emoji']} {s['name']}\n"
            f"Country: {c['name']}\n"
            f"Amount: *~${usdt} USDT* (≈₹{c['price']})\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Address ({USDT_NET}):\n`{USDT_ADDR}`\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"1️⃣ Send USDT to above address\n"
            f"2️⃣ Take screenshot of txn\n"
            f"3️⃣ Click *I've Paid* & send screenshot\n\n"
            f"⚠️ Only *{USDT_NET}* network!"
        )
    await q.edit_message_text(text, parse_mode='Markdown', reply_markup=paid_kb(method, svc_key, ctry_key))

async def cb_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split('_', 3)  # paid_upi_whatsapp_iraq
    method, svc_key, ctry_key = parts[1], parts[2], parts[3]
    context.user_data['pending'] = {'method': method, 'svc': svc_key, 'ctry': ctry_key}
    await q.edit_message_text(
        "📸 *Send Payment Screenshot*\n\n"
        "Please send a clear screenshot/photo of your payment proof.\n\n"
        "⏰ Admin will verify within few minutes.\n"
        "Your number will be delivered instantly after approval!\n\n"
        "Type /cancel to cancel.",
        parse_mode='Markdown'
    )
    return WAITING_PROOF

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending = context.user_data.get('pending')
    if not pending:
        await update.message.reply_text("❌ Session expired. /start again.")
        return ConversationHandler.END

    if update.message.photo:
        file_id = update.message.photo[-1].file_id; is_photo = True
    elif update.message.document:
        file_id = update.message.document.file_id; is_photo = False
    else:
        await update.message.reply_text("⚠️ Please send a photo/screenshot of payment.")
        return WAITING_PROOF

    method, svc_key, ctry_key = pending['method'], pending['svc'], pending['ctry']
    c = COUNTRIES[ctry_key]; s = SERVICES[svc_key]
    oid = create_order(user.id, svc_key, ctry_key, method, file_id)

    await update.message.reply_text(
        f"✅ *Order Placed Successfully!*\n\n"
        f"┌─────────────────────\n"
        f"│ Order ID: `#{oid}`\n"
        f"│ App: {s['emoji']} {s['name']}\n"
        f"│ Country: {c['name']}\n"
        f"│ Amount: ₹{c['price']}\n"
        f"│ Payment: {method.upper()}\n"
        f"│ Status: ⏳ Pending Verification\n"
        f"└─────────────────────\n\n"
        f"📲 You'll get the number once admin approves!\n"
        f"Track your order: /myorders",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Track Order", callback_data="my_orders")
        ]])
    )

    # Admin notification
    uname = f"@{user.username}" if user.username else f"ID:{user.id}"
    cap = (
        f"🔔 *NEW ORDER #{oid}*\n\n"
        f"👤 {user.first_name} ({uname})\n"
        f"🆔 User ID: `{user.id}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📱 App: {s['emoji']} {s['name']}\n"
        f"🌍 Country: {c['name']}\n"
        f"💰 Price: ₹{c['price']}\n"
        f"💳 Method: {method.upper()}\n"
        f"⏰ Time: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━"
    )
    if is_photo:
        await context.bot.send_photo(ADMIN_ID, photo=file_id, caption=cap,
                                      parse_mode='Markdown', reply_markup=admin_kb(oid))
    else:
        await context.bot.send_document(ADMIN_ID, document=file_id, caption=cap,
                                         parse_mode='Markdown', reply_markup=admin_kb(oid))
    context.user_data.pop('pending', None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('pending', None)
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_kb())
    return ConversationHandler.END

async def cb_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    orders = get_user_orders(q.from_user.id)
    if not orders:
        text = "📋 *My Orders*\n\nNo orders yet!\nTap Buy Number to get started 🚀"
    else:
        text = "📋 *My Orders* (Last 10)\n━━━━━━━━━━━━━━━\n\n"
        for o in orders:
            em = STATUS_EMOJI.get(o['status'], '❓')
            svc = SERVICES.get(o.get('service', ''), {}).get('name', o.get('service', 'N/A'))
            text += f"{em} *Order #{o['id']}*\n"
            text += f"   📱 {svc} | {o['country_name']}\n"
            text += f"   ₹{o['price']} | {o['status'].upper()}\n"
            if o['number_delivered']:
                text += f"   📞 Number: `{o['number_delivered']}`\n"
            text += "\n"
    await q.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]))

async def cb_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = (
        "💰 *Price List*\n━━━━━━━━━━━━━━━\n\n"
        "✅ Standard Numbers — *₹79*\n"
        "🔥 Fresh/New Numbers — *₹99*\n\n"
        "📱 *Available for:*\n"
    )
    for s in SERVICES.values():
        text += f"  {s['emoji']} {s['name']}\n"
    text += "\n🌍 *18+ Countries Available*\n\n📩 Instant Delivery after approval"
    await q.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buy Now", callback_data="buy")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]))

async def my_orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_user_orders(update.effective_user.id)
    if not orders:
        text = "📋 *My Orders*\n\nNo orders yet! Use /start to buy."
    else:
        text = "📋 *My Orders* (Last 10)\n━━━━━━━━━━━━━━━\n\n"
        for o in orders:
            em = STATUS_EMOJI.get(o['status'], '❓')
            svc = SERVICES.get(o.get('service', ''), {}).get('name', 'N/A')
            text += f"{em} *Order #{o['id']}* — {svc} | {o['country_name']}\n"
            text += f"   ₹{o['price']} | {o['status'].upper()}\n"
            if o['number_delivered']:
                text += f"   📞 `{o['number_delivered']}`\n"
            text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ─── Admin Handlers ───────────────────────────────────────────────────────────
async def cb_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔ Unauthorized", show_alert=True); return
    await q.answer()
    oid = int(q.data.split('_')[1])
    order = get_order(oid)
    if not order:
        await q.answer("Not found", show_alert=True); return
    if order['status'] != 'pending':
        await q.answer(f"Already {order['status']}", show_alert=True); return

    update_order(oid, 'approved')
    if 'pnum' not in context.bot_data: context.bot_data['pnum'] = {}
    context.bot_data['pnum'][ADMIN_ID] = oid

    await q.edit_message_caption(
        caption=(q.message.caption or '') + f"\n\n✅ *APPROVED*\n📤 Send the number for Order #{oid}:",
        parse_mode='Markdown'
    )
    await context.bot.send_message(
        order['user_id'],
        f"✅ *Payment Verified!*\n\n"
        f"Order `#{oid}` approved!\n"
        f"Your number is being prepared... 🔄",
        parse_mode='Markdown'
    )

async def cb_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔ Unauthorized", show_alert=True); return
    await q.answer()
    oid = int(q.data.split('_')[1])
    order = get_order(oid)
    if not order: return

    update_order(oid, 'rejected')
    await q.edit_message_caption(
        caption=(q.message.caption or '') + "\n\n❌ *REJECTED*", parse_mode='Markdown'
    )
    await context.bot.send_message(
        order['user_id'],
        f"❌ *Order Rejected*\n\nOrder `#{oid}` — Payment not verified.\nContact support if you believe this is an error.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{SUPPORT_USER}")
        ]])
    )

async def admin_deliver_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    oid = context.bot_data.get('pnum', {}).get(ADMIN_ID)
    if not oid: return

    number = update.message.text.strip()
    order = get_order(oid)
    if not order:
        await update.message.reply_text("❌ Order not found!"); return

    update_order(oid, 'delivered', number=number)
    context.bot_data['pnum'].pop(ADMIN_ID, None)
    svc = SERVICES.get(order.get('service', ''), {})

    await context.bot.send_message(
        order['user_id'],
        f"🎉 *Number Delivered!*\n\n"
        f"┌─────────────────────\n"
        f"│ Order: `#{oid}`\n"
        f"│ App: {svc.get('emoji','')} {svc.get('name','')}\n"
        f"│ Country: {order['country_name']}\n"
        f"│ 📞 Number: `{number}`\n"
        f"└─────────────────────\n\n"
        f"✅ Use this number to receive your OTP!\n"
        f"If you face any issue, contact support 👇",
        parse_mode='Markdown', reply_markup=after_delivery_kb()
    )
    await update.message.reply_text(f"✅ Delivered Order #{oid} → `{number}`", parse_mode='Markdown')

async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    orders = get_pending_orders()
    if not orders:
        await update.message.reply_text("✅ No pending orders!"); return
    text = f"📋 *Pending Orders ({len(orders)})*\n━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        svc = SERVICES.get(o.get('service',''), {}).get('name', 'N/A')
        text += f"#️⃣ *#{o['id']}* | {svc} | {o['country_name']} | ₹{o['price']} | {o['payment_method'].upper()}\n   UID: {o['user_id']}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    total, rev, pend, users = get_stats()
    await update.message.reply_text(
        f"📊 *{BOT_NAME} — Statistics*\n━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Users: *{users}*\n"
        f"✅ Delivered Orders: *{total}*\n"
        f"💰 Total Revenue: *₹{rev}*\n"
        f"⏳ Pending Orders: *{pend}*",
        parse_mode='Markdown'
    )

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    context.bot_data.get('pnum', {}).pop(ADMIN_ID, None)
    await update.message.reply_text("✅ Delivery skipped.")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_paid, pattern='^paid_')],
        states={WAITING_PROOF: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof)]},
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myorders', my_orders_cmd))
    app.add_handler(CommandHandler('orders', cmd_orders))
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('skip', cmd_skip))
    app.add_handler(CommandHandler('cancel', cancel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(cb_main_menu, pattern='^main_menu$'))
    app.add_handler(CallbackQueryHandler(cb_buy,       pattern='^buy$'))
    app.add_handler(CallbackQueryHandler(cb_service,   pattern='^svc_'))
    app.add_handler(CallbackQueryHandler(cb_country,   pattern='^ctry_'))
    app.add_handler(CallbackQueryHandler(cb_payment,   pattern='^pay_'))
    app.add_handler(CallbackQueryHandler(cb_my_orders, pattern='^my_orders$'))
    app.add_handler(CallbackQueryHandler(cb_prices,    pattern='^prices$'))
    app.add_handler(CallbackQueryHandler(cb_approve,   pattern='^approve_'))
    app.add_handler(CallbackQueryHandler(cb_reject,    pattern='^reject_'))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID),
        admin_deliver_number
    ))

    logger.info(f"🤖 {BOT_NAME} running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
