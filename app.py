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
CACHE_TTL = 300  # 5 minutes


# ==============================
# 🔄 CACHE REFRESH
# ==============================
def refresh_cache():
    global cache, last_updated

    try:
        records = sheet.get_all_records()
        headers = records[0]
        rows = records[1:]

        new_cache = {}

        for row in rows:
            data = dict(zip(headers, row))

            # Normalize keys
            mobile = str(data.get("Customer Mobile") or "").strip()
            email = str(data.get("Customer Email") or "").strip().lower()

            mobile = mobile.replace(" ", "").replace("+91", "")

            keys = [mobile, email]

            for key in keys:
                if key:
                    if key not in new_cache:
                        new_cache[key] = []
                    new_cache[key].append(data)

        cache = new_cache
        last_updated = time.time()

        print(f"✅ Cache refreshed: {len(cache)} users")

    except Exception as e:
        print("❌ Cache error:", str(e))


# ==============================
# ⚡ ASYNC REFRESH
# ==============================
def refresh_cache_async():
    thread = threading.Thread(target=refresh_cache)
    thread.daemon = True
    thread.start()


def get_cached_data():
    if time.time() - last_updated > CACHE_TTL:
        refresh_cache_async()
    return cache


# ==============================
# ✂️ HELPER
# ==============================
def get_short_product(name):
    if not name:
        return ""
    return name[:40]


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

        # Normalize input
        query = query.replace(" ", "").replace("+91", "")

        if not query:
            return jsonify({"status": "Invalid query"})

        data_cache = get_cached_data()
        rows = data_cache.get(query)

        if not rows:
            return jsonify({"status": "Not Found"})

        orders = []

        for row in rows:
            awb_raw = str(
                row.get("AWB Code") or 
                row.get("AWB") or ""
            ).strip()

            awb = awb_raw if awb_raw else None

            order = {
                "awb": awb,
                "status": str(row.get("Status") or "").strip() or "Pending",
                "courier": str(row.get("Courier Company") or "").strip() or "Not Assigned",
                "product": get_short_product(
                    row.get("Product Name") or ""
                ) or "Not Available",
                "created_at": str(
                    row.get("Shiprocket Created At") or ""
                ).strip() or "Not Available",
                "tracking_link": f"https://shiprocket.co/tracking/{awb}" if awb else None
            }

            orders.append(order)

        return jsonify({
            "count": len(orders),
            "orders": list(reversed(orders))  # latest first
        })

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"status": "Error", "message": str(e)})


# ==============================
# 🚀 PRELOAD CACHE
# ==============================
refresh_cache()

# ==============================
# ▶️ RUN
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
