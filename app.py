import os
import json
import time
import threading
import requests
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
# 🔴 REDASH CONFIG
# ==============================
REDASH_API_KEY = os.environ.get("MuksNDK1QVDm6BTBQZzMAcjBzGsY42vi7xyof4yz")
REDASH_QUERY_ID = os.environ.get("19923")
REDASH_BASE_URL = os.environ.get("https://data.testbook.com/queries/")

def check_preorder_from_redash(query):
    try:
        url = f"{REDASH_BASE_URL}/api/queries/{REDASH_QUERY_ID}/results.json"

        headers = {
            "Authorization": f"Key {REDASH_API_KEY}"
        }

        params = {
            "api_key": REDASH_API_KEY,
            "p_query": query   # 🔥 change if your parameter name is different
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)
        data = res.json()

        rows = data.get("query_result", {}).get("data", {}).get("rows", [])

        for row in rows:
            status = str(row.get("status", "")).lower()

            if "pre order" in status:
                return True

        return False

    except Exception as e:
        print("❌ Redash error:", str(e))
        return False

# ==============================
# 🚀 CACHE CONFIG
# ==============================
cache = {}
last_updated = 0
CACHE_TTL = 1800  # 30 minutes

# ==============================
# ✂️ HELPER FUNCTIONS
# ==============================
def normalize(value):
    return str(value).strip().lower().replace(" ", "").replace("+91", "")

def get_short_product(name):
    return name[:40] if name else ""

# ==============================
# 🔄 CACHE REFRESH
# ==============================
def refresh_cache():
    global cache, last_updated

    try:
        records = sheet.get_all_records()

        new_cache = {}

        for data in records:
            mobile = normalize(data.get("Customer Mobile"))
            email = normalize(data.get("Customer Email"))

            keys = [mobile, email]

            for key in keys:
                if key:
                    new_cache.setdefault(key, []).append(data)

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
# 🏠 ROUTES
# ==============================
@app.route("/")
def home():
    return "API is running 🚀"

@app.route("/search", methods=["POST"])
def search():
    try:
        data = request.get_json(silent=True) or {}
        query = normalize(data.get("query", ""))

        if not query:
            return jsonify({"status": "Invalid query"})

        data_cache = get_cached_data()
        rows = data_cache.get(query)

        # ==============================
        # ✅ IF FOUND IN SHEET
        # ==============================
        if rows:
            orders = []

            for row in rows:
                awb_raw = str(
                    row.get("AWB Code") or 
                    row.get("AWB") or ""
                ).strip()

                awb = awb_raw if awb_raw else None

                orders.append({
                    "awb": awb,
                    "status": row.get("Status", "").strip() or "Pending",
                    "courier": row.get("Courier Company", "").strip() or "Not Assigned",
                    "product": get_short_product(row.get("Product Name", "")) or "Not Available",
                    "created_at": row.get("Shiprocket Created At", "").strip() or "Not Available",
                    "edd": str(row.get("EDD") or "").strip() or "Not Available",
                    "tracking_link": f"https://shiprocket.co/tracking/{awb}" if awb else None
                })

            return jsonify({
                "count": len(orders),
                "orders": list(reversed(orders))
            })

        # ==============================
        # 🔥 FALLBACK → REDASH
        # ==============================
        is_preorder = check_preorder_from_redash(query)

        if is_preorder:
            return jsonify({
                "count": 1,
                "orders": [{
                    "awb": None,
                    "status": "Pre Order",
                    "courier": "Not Available",
                    "product": "Not Available",
                    "created_at": "Not Available",
                    "edd": "Not Available",
                    "tracking_link": None
                }]
            })

        return jsonify({"status": "Not Found"})

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"status": "Error", "message": str(e)})

# ==============================
# 🔄 MANUAL REFRESH
# ==============================
@app.route("/refresh")
def manual_refresh():
    refresh_cache_async()
    return "Cache refresh started 🚀"

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
