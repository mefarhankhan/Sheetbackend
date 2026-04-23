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
REDASH_API_KEY = os.environ.get("REDASH_API_KEY")
REDASH_QUERY_ID = "19923"
REDASH_BASE_URL = "https://data.testbook.com"

# ==============================
# ✂️ HELPER FUNCTIONS
# ==============================
def last10(val):
    v = str(val).strip().replace(" ", "").replace("+", "")
    return v[-10:] if len(v) >= 10 else v

def get_short_product(name):
    return name[:40] if name else ""

# ==============================
# 🔴 REDASH SEARCH
# ==============================
def check_status_from_redash(query):
    try:
        url = f"{REDASH_BASE_URL}/api/queries/{REDASH_QUERY_ID}/results.json"

        headers = {
            "Authorization": f"Key {REDASH_API_KEY}"
        }

        res = requests.get(url, headers=headers, timeout=15)

        print("🔴 Status Code:", res.status_code)

        if res.status_code != 200:
            print("❌ Redash failed:", res.text)
            return None

        data = res.json()
        rows = data.get("query_result", {}).get("data", {}).get("rows", [])

        print("🔴 Total rows:", len(rows))

        q = last10(query)

        for row in rows:
            mobile = last10(row.get("mobile", ""))
            email = str(row.get("email", "")).strip().lower()

            if q == mobile or q == email:
                status = str(
                    row.get("shippingStatus") or 
                    row.get("shipping_status") or 
                    row.get("status") or 
                    ""
                ).strip()

                print("✅ MATCH FOUND:", status)
                return status if status else "Not Available"

        print("❌ No match in Redash")
        return None

    except Exception as e:
        print("❌ Redash error:", str(e))
        return None

# ==============================
# 🚀 CACHE CONFIG
# ==============================
cache = {}
last_updated = 0
CACHE_TTL = 1800  # 30 minutes

# ==============================
# 🔄 CACHE REFRESH
# ==============================
def refresh_cache():
    global cache, last_updated

    try:
        records = sheet.get_all_records()
        new_cache = {}

        for data in records:
            mobile_raw = str(data.get("Customer Mobile", "")).strip()
            email = str(data.get("Customer Email", "")).strip().lower()

            m10 = last10(mobile_raw)

            keys = []

            if m10:
                keys.append(m10)

            if email:
                keys.append(email)

            for key in keys:
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

        query_raw = data.get("query", "")
        query_mobile = last10(query_raw)
        query_email = str(query_raw).strip().lower()

        if not query_raw:
            return jsonify({"status": "Invalid query"})

        data_cache = get_cached_data()

        # ==============================
        # ✅ SHEET SEARCH
        # ==============================
        rows = data_cache.get(query_mobile) or data_cache.get(query_email)

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
        # 🔥 REDASH FALLBACK
        # ==============================
        status = check_status_from_redash(query_raw)

        if status:
            return jsonify({
                "count": 1,
                "orders": [{
                    "awb": None,
                    "status": status,
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
