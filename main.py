import websocket
import threading
import time
import json
import requests
from datetime import datetime
import html
import os
from flask import Flask, Response

# -------------------- CONFIG --------------------
PING_INTERVAL = int(os.environ.get("PING_INTERVAL", 25))
start_pinging = False

# Env Variables
WS_URL = os.environ.get("WS_URL")
AUTH_MESSAGE = os.environ.get("AUTH_MESSAGE")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = os.environ.get("GROUP_ID")
CHANNEL_URL = os.environ.get("CHANNEL_URL")
DEV_URL = os.environ.get("DEV_URL")
Support = os.environ.get("Support")

# -------------------- TELEGRAM --------------------
def send_to_telegram(text, retries=3, delay=5):
    buttons = {
        "inline_keyboard": [
            [
                {"text": "📱Numbers", "url": CHANNEL_URL},
                {"text": "💻 Developer", "url": DEV_URL}
            ],
            [
                {"text": "🛠 Support", "url": Support}
            ]
        ]
    }

    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(buttons)
    }

    for attempt in range(retries):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data=payload,
                timeout=10
            )
            if response.status_code == 200:
                print("✅ Message sent to Telegram")
                return True
            else:
                print(f"⚠️ Telegram Error [{response.status_code}]: {response.text}")
        except Exception as e:
            print(f"❌ Telegram Send Failed (Attempt {attempt+1}/{retries}):", e)
        
        if attempt < retries - 1:
            time.sleep(delay)
    return False

# -------------------- FUNCTIONS --------------------
def send_ping(ws):
    global start_pinging
    while ws.keep_running:
        if start_pinging:
            try:
                ws.send("3")
                print("📡 Ping sent (3)")
            except Exception as e:
                print("❌ Failed to send ping:", e)
                break
        time.sleep(PING_INTERVAL)

def on_open(ws):
    global start_pinging
    start_pinging = False
    print("✅ WebSocket connected")

    time.sleep(0.5)
    ws.send("40/livesms")
    print("➡️ Sent: 40/livesms")

    time.sleep(0.5)
    ws.send(AUTH_MESSAGE)
    print("🔐 Sent auth token")

    threading.Thread(target=send_ping, args=(ws,), daemon=True).start()

def on_message(ws, message):
    global start_pinging
    if message == "3":
        print("✅ Pong received")
    elif message.startswith("40/livesms"):
        print("✅ Namespace joined — starting ping")
        start_pinging = True
    elif message.startswith("42/livesms,"):
        try:
            payload = message[len("42/livesms,"):]
            data = json.loads(payload)

            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
                sms = data[1]
                raw_msg = sms.get("message", "")
                originator = sms.get("originator", "Unknown")
                recipient = sms.get("recipient", "")
                country = sms.get("country_iso", "??").upper()

                import re
                otp_match = re.search(r'\b\d{3}[- ]?\d{3}\b|\b\d{6}\b', raw_msg)
                otp = otp_match.group(0) if otp_match else "N/A"

                # Masked number fix
                if recipient and len(recipient) >= 4:
                    masked_number = "⁕" * (len(recipient) - 4) + recipient[-4:]
                else:
                    masked_number = "Unknown"

                now = datetime.now().strftime("%H:%M:%S")
                service = "WhatsApp" if "whatsapp" in raw_msg.lower() else "Unknown"

                # New message format
                telegram_msg = (
                    "🔔 <b><u>Real-Time OTP Alert</u></b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🌐 <b>Country:</b> <code>{country}</code>\n"
                    f"🪪 <b>Originator:</b> <code>{originator}</code>\n"
                    f"🔢 <b>OTP Code:</b> <code>{otp}</code>\n"
                    f"⏰ <b>Received At:</b> <code>{now}</code>\n"
                    f"📱 <b>Recipient:</b> <code>{masked_number}</code>\n"
                    f"⚙️ <b>Service:</b> <code>{service}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📝 <b>Full Message:</b>\n"
                    f"<code>{html.escape(raw_msg)}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📡 <i>Sponsored by UN Secure OTP Platform</i>"
                )

                send_to_telegram(telegram_msg)
            else:
                print("⚠️ Unexpected data format:", data)

        except Exception as e:
            print("❌ Error parsing message:", e)
            print("Raw message:", message)

def on_error(ws, error):
    print("❌ WebSocket error:", error)

def on_close(ws, code, msg):
    global start_pinging
    start_pinging = False
    print("🔌 WebSocket closed. Reconnecting in 1s...")
    time.sleep(1)
    start_ws_thread()

def connect():
    print("🔄 Connecting to IVASMS WebSocket...")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://ivasms.com",
        "Referer": "https://ivasms.com/",
        "Host": "ivasms.com"
    }

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header=[f"{k}: {v}" for k, v in headers.items()]
    )

    ws.run_forever()

def start_ws_thread():
    t = threading.Thread(target=connect, daemon=True)
    t.start()

# -------------------- FLASK WEB SERVICE --------------------
app = Flask(__name__)

@app.route("/")
def root():
    return Response("Service is running", status=200)

@app.route("/health")
def health():
    return Response("OK", status=200)

# -------------------- START --------------------
if __name__ == "__main__":
    start_ws_thread()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)
