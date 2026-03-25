import os
import json
import time
import threading
import gspread
from flask import Flask, request, jsonify
from flask_cors import CORS
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
CORS(app)

# ==============================
# 🔐 Google API Setup
# ==============================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("BOOK QUERIES").worksheet("All orders")

# ==============================
# 🚀 CACHE CONFIG
# ==============================
cache = {}
last_updated = 0
CACHE_TTL = 300  # 5 minutes (increase if needed)

# ==============================
# 🔄 CACHE REFRESH (FAST)
# ==============================
def refresh_cache():
    global cache, last_updated

    try:
        records = sheet.get_all_values()  # ⚡ faster than get_all_records
        headers = records[0]
        rows = records[1:]

        new_cache = {}

        for row in rows:
            data = dict(zip(headers, row))

            mobile = str(data.get("Customer Mobile") or "").strip().lower()
            email = str(data.get("Customer Email") or "").strip().lower()

            if mobile:
                new_cache[mobile] = data
            if email:
                new_cache[email] = data

        cache = new_cache
        last_updated = time.time()

        print(f"✅ Cache refreshed: {len(cache)} entries")

    except Exception as e:
        print("❌ Cache refresh error:", str(e))


# ==============================
# ⚡ NON-BLOCKING REFRESH
# ==============================
def refresh_cache_async():
    thread = threading.Thread(target=refresh_cache)
    thread.daemon = True
    thread.start()


def get_cached_data():
    global last_updated

    # If expired → refresh in background
    if time.time() - last_updated > CACHE_TTL:
        refresh_cache_async()

    return cache


# ==============================
# 🏠 ROUTES
# ==============================
@app.route("/")
def home():
    return "API is running 🚀"


@app.route("/search", methods=["POST"])
def search():
    try:
        data = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip().lower()

        if not query:
            return jsonify({"status": "Invalid query"})

        data_cache = get_cached_data()
        row = data_cache.get(query)

        if not row:
            return jsonify({"status": "Not Found"})

        awb = str(row.get("AWB Code") or "").strip()
        status = str(row.get("Status") or "").strip()
        courier = str(row.get("Courier Company") or "").strip()

        tracking_link = f"https://shiprocket.co/tracking/{awb}" if awb else ""

        return jsonify({
            "status": status,
            "courier": courier,
            "awb": awb or "Not available",
            "tracking_link": tracking_link
        })

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"status": "Error", "message": str(e)})


# ==============================
# 🚀 PRELOAD CACHE (IMPORTANT)
# ==============================
refresh_cache()

# ==============================
# ▶️ RUN APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
