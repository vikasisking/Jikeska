import logging
import requests
import threading
import time
import os
from flask import Flask, Response
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import html

last_change_time = {}

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", -1002091416812))
API_URL = "https://raazit.acchub.io/api/"
BASE_URL = "https://raazit.acchub.io/api/sms"
FETCH_INTERVAL = 2  # seconds
ADMIN_ID = int(os.getenv("ADMIN_ID", 6884253109)) 
ADMIN_IDs = int(os.getenv("ADMIN_IDs", 7761576669))  ## Add admin ID for /hiden_25 command
#ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "7761576669", "6884253109").split(",")]
DEV_LINK = os.getenv("DEV_LINK", "https://t.me/hiden_25")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+2P-OUmWo1hc0NmNh")
Support = os.getenv("Support", "https://t.me/OpxAli")
# Required channels for force join
REQUIRED_CHANNELS = [
    "@BlackHatsssss",
    #"@+UyoEvMS5XAxkNTc0",
    #"@+2P-OUmWo1hc0NmNh",
   # "@fasttech3",
    "@h2icoder",
    "@freeotpss"
]
#channel2 = [ "@+F4Md7IotaqcxN2I9" ]
# Store user IDs who have started the bot
USER_IDS = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== Flask App for Render Health Checks ======
app = Flask(__name__)

@app.route("/health")
def health():
    logger.info("Health check requested")
    return Response("OK", status=200)

@app.route("/")
def root():
    logger.info("Root endpoint requested")
    return Response("OK", status=200)

# ====== Function to Check Channel Membership ======
async def check_membership(user_id, context: ContextTypes.DEFAULT_TYPE):
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}")
            return False
    return True

# ====== Function to Generate Join Channel Message ======
def get_join_channel_message():
    keyboard = []
    for channel in REQUIRED_CHANNELS:
        # Handle chat IDs (starting with -100) vs usernames (starting with @)
        if channel.startswith("@"):
            url = f"https://t.me/{channel[1:]}"
        else:
            url = f"https://t.me/c/{channel.replace('-100', '')}"  # For private channels with chat IDs
        keyboard.append([InlineKeyboardButton(f"Join {channel}", url=url)])
       # keyboard.append([InlineKeyboardButton(f"Join {channel2}", url=url)])
    keyboard.append([InlineKeyboardButton("✅ Check Membership", callback_data="check_membership")])
    return (
        "Join Main Channel https://t.me/+2P-OUmWo1hc0NmNh\n"
        "⚠️ <b>Please join all required channels to use this bot!</b>\n\n"
        "Click the buttons below to join the channels, then press 'Check Membership'.\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Powered by @OpxAli And bot dev @hiden_25 ❤️</i>"
    ), InlineKeyboardMarkup(keyboard)

# ====== Stats Command ======
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    total_users = len(USER_IDS)
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Powered by @OpxAli And bot dev @hiden_25 ❤️</i>",
        parse_mode="HTML"
    )
# ====== acchubb.py ka OTP monitor ========
def mask_number(num):
    num = str(num)
    if len(num) > 5:
        return num[:2] + '*' * (len(num) - 5) + num[-3:]
    return num

def fetch_otp_acchubb():
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "auth-token": AUTH_TOKEN,
        "Cookie": f"authToken={AUTH_TOKEN}; authRole=Freelancer",
        "Origin": "https://raazit.acchub.io",
        "Referer": "https://raazit.acchub.io",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0"
    }
    data = {
        "action": "get_otp",
        "number": "1234567890"
    }
    try:
        response = requests.post(API_URL, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.error(f"Error fetching OTP: {e}")
    return []

def send_telegram_message(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👨‍💻 Developer", "url": DEV_LINK},
                    {"text": "📢 Channel", "url": CHANNEL_LINK}
                ],
                [
                    {"text": "👑 Owner", "url": Support}
                ]
            ]
        }
        payload = {
            "chat_id": GROUP_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": str(keyboard).replace("'", '"')
        }
        r = requests.post(url, data=payload)
        if r.status_code == 200:
            logger.info("✅ OTP sent to Telegram")
        else:
            logger.error(f"❌ Telegram send failed: {r.text}")
    except Exception as e:
        logger.error(f"⚠️ Telegram error: {e}")

def otp_monitor_acchubb():
    logger.info("Starting OTP monitor thread")
    sent_ids = set()
    for otp_entry in fetch_otp_acchubb():
        otp_id = otp_entry.get("id")
        otp_code = otp_entry.get("otp", "").strip()
        if otp_code:
            sent_ids.add(otp_id)
            msg = (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📩 <b>New OTP Notification</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📞 <b>Number:</b> <code>{mask_number(otp_entry.get('did'))}</code>\n"
                f"🌍 <b>Country:</b> <b>{otp_entry.get('country_name')}</b>\n\n"
                f"🔑 <b>OTP:</b> <blockquote>{html.escape(otp_code)}</blockquote>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚡️ <i>Powered by @OpxAli Bot dev @hiden_25 🔱</i>\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
            send_telegram_message(msg)
    while True:
        for otp_entry in fetch_otp_acchubb():
            otp_id = otp_entry.get("id")
            otp_code = otp_entry.get("otp", "").strip()
            if otp_code and otp_id not in sent_ids:
                sent_ids.add(otp_id)
                msg = (
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📩 <b>New OTP Notification</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📞 <b>Number:</b> <code>{mask_number(otp_entry.get('did'))}</code>\n"
                    f"🌍 <b>Country:</b> <b>{otp_entry.get('country_name')}</b>\n\n"
                    f"🔑 <b>OTP:</b> <blockquote>{html.escape(otp_code)}</blockquote>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡️ <i>Powered by @OpxAli Bot Dev @hiden_25 ❤️</i>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                send_telegram_message(msg)
        time.sleep(FETCH_INTERVAL)

# ====== acc.py ka number add bot =========
def get_countries():
    headers = {"Auth-Token": AUTH_TOKEN}
    resp = requests.get(f"{BASE_URL}/combo-list", headers=headers)
    data = resp.json()
    return data.get("data", []) if data.get("meta") == 200 else []

def get_carriers(country_id):
    headers = {"Auth-Token": AUTH_TOKEN}
    resp = requests.get(f"{BASE_URL}/carrier-list?app={country_id}", headers=headers)
    data = resp.json()
    return data.get("data", []) if data.get("meta") == 200 else []

def add_number(app_id, carrier_id):
    headers = {
        "Auth-Token": AUTH_TOKEN,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }
    data = {
        "authToken": AUTH_TOKEN,
        "app": app_id,
        "carrier": carrier_id
    }
    return requests.post(f"{BASE_URL}/", headers=headers, files={}, data=data).json()

# Memory store for user preferences
user_last_selection = {}
COUNTRIES_PER_PAGE = 10

def paginate_countries(page=0):
    countries = get_countries()
    start = page * COUNTRIES_PER_PAGE
    end = start + COUNTRIES_PER_PAGE
    buttons = [
        [InlineKeyboardButton(c["text"], callback_data=f"country|{c['id']}")]
        for c in countries[start:end]
    ]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅ Back", callback_data=f"more_countries|{page-1}"))
    if end < len(countries):
        nav_buttons.append(InlineKeyboardButton("➡ More", callback_data=f"more_countries|{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    return buttons

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Store user ID
    USER_IDS.add(update.effective_user.id)
    # Check if user is a member of required channels
    user_id = update.effective_user.id
    if not await check_membership(user_id, context):
        msg, reply_markup = get_join_channel_message()
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        return
    keyboard = paginate_countries(0)
    await update.message.reply_text("🌍 Select a country:", reply_markup=InlineKeyboardMarkup(keyboard))

async def search_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_membership(user_id, context):
        msg, reply_markup = get_join_channel_message()
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        return
    if not context.args:
        await update.message.reply_text("🔍 Usage: /search <country name>")
        return
    query = " ".join(context.args).lower()
    countries = get_countries()
    matched = [c for c in countries if query in c["text"].lower()]
    if not matched:
        await update.message.reply_text("❌ Country not found.")
        return
    if len(matched) > 1:
        keyboard = [[InlineKeyboardButton(c["text"], callback_data=f"country|{c['id']}")] for c in matched]
        await update.message.reply_text("🌍 Select a country:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    country = matched[0]
    carriers = get_carriers(country["id"])
    if not carriers:
        res = add_number(country["id"], "")
        if res.get("meta") == 200 and res.get("data"):
            await send_number_message(update, res["data"], country["id"], "")
        else:
            await update.message.reply_text("❌ Numbers currently not available.")
        return
    keyboard = [
        [InlineKeyboardButton(c["text"], callback_data=f"carrier|{country['id']}|{c['id']}")]
        for c in carriers
    ]
    await update.message.reply_text("🚚 Select a carrier:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, *values = query.data.split("|")

    if action == "check_membership":
        user_id = query.from_user.id
        if await check_membership(user_id, context):
            keyboard = paginate_countries(0)
            await query.edit_message_text("🌍 Select a country:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            msg, reply_markup = get_join_channel_message()
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        return

    user_id = query.from_user.id
    if not await check_membership(user_id, context):
        msg, reply_markup = get_join_channel_message()
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        return

    if action == "more_countries":
        page = int(values[0])
        keyboard = paginate_countries(page)
        await query.edit_message_text("🌍 Select a country:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "country":
        country_id = values[0]
        carriers = get_carriers(country_id)
        if not carriers:
            res = add_number(country_id, "")
            if res.get("meta") == 200 and res.get("data"):
                data = res["data"]
                user_last_selection[query.from_user.id] = (country_id, "")
                await send_number_message(query, data, country_id, "")
            else:
                await query.edit_message_text("❌ Numbers currently not available.")
            return
        keyboard = [
            [InlineKeyboardButton(c["text"], callback_data=f"carrier|{country_id}|{c['id']}")]
            for c in carriers
        ]
        await query.edit_message_text("🚚 Select a carrier:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "carrier":
        country_id, carrier_id = values
        res = add_number(country_id, carrier_id)
        if res.get("meta") == 200 and res.get("data"):
            data = res["data"]
            user_last_selection[query.from_user.id] = (country_id, carrier_id)
            await send_number_message(query, data, country_id, carrier_id)
        else:
            await query.edit_message_text("❌ Numbers currently not available.")

    elif action == "change_number":
        if query.from_user.id not in user_last_selection:
            await query.edit_message_text("❌ First get a number.")
            return
        country_id, carrier_id = user_last_selection[query.from_user.id]
        res = add_number(country_id, carrier_id)
        if res.get("meta") == 200 and res.get("data"):
            data = res["data"]
            await send_number_message(query, data, country_id, carrier_id, changed=True)
        else:
            await query.edit_message_text("❌ Numbers currently not available.")

async def send_number_message(query, data, country_id, carrier_id, changed=False):
    msg = (
        ("🔄 <b>Number Changed!</b>\n\n" if changed else "✅ <b>Number Added Successfully!</b>\n\n") +
        f"📞 <b>Number:</b> <code>{data.get('did')}</code>\n"
        f"<i>Developed by @OpxAli Bot Dev @hiden_25 ❤️</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("📩 View OTP", url="https://t.me/BlackHatsssss"),
            InlineKeyboardButton("📢 Main Channel", url="https://t.me/+2P-OUmWo1hc0NmNh")
        ],
        [
            InlineKeyboardButton("🔄 Change Number", callback_data="change_number")
        ]
    ]
    await query.edit_message_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ====== New /hiden_25 Command for Broadcasting ======
async def hiden_25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_IDs:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("🔍 Usage: /hiden_25 <message>")
        return

    broadcast_message = " ".join(context.args)
    broadcast_message = (
        "📢 <b>Broadcast Message</b>\n\n"
        f"{html.escape(broadcast_message)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Powered by @OpxAli Bot dev @hiden_25 ❤️</i>"
    )
    sent_count = 0
    failed_count = 0

    for user_id in USER_IDS:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_message,
                parse_mode="HTML"
            )
            sent_count += 1
            logger.info(f"✅ Broadcast sent to user {user_id}")
            # Add delay to avoid hitting Telegram rate limits (approx 30 messages/sec)
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"❌ Failed to send broadcast to user {user_id}: {e}")
            failed_count += 1

    await update.message.reply_text(
        f"📩 Broadcast completed!\n"
        f"✅ Sent to {sent_count} users\n"
        f"❌ Failed for {failed_count} users"
    )

def start_otp_thread():
    threading.Thread(target=otp_monitor_acchubb, daemon=True).start()

def start_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_country))
    application.add_handler(CommandHandler("hiden_25", hiden_25))  # Add new command handler
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button))
    application.run_polling()

if __name__ == "__main__":
    logger.info("Starting application...")
    start_otp_thread()
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), threaded=True),
        daemon=True
    ).start()
    start_bot()
