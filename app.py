import os
import json
import time
import gspread
from flask import Flask, request, jsonify
from flask_cors import CORS
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
CORS(app)

# Google API setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("BOOK QUERIES").worksheet("All orders")

# 🚀 CACHE
cache = {}
last_updated = 0
CACHE_TTL = 60  # seconds


def refresh_cache():
    global cache, last_updated

    records = sheet.get_all_records()
    new_cache = {}

    for row in records:
        mobile = str(row.get("Customer Mobile") or "").strip()
        email = str(row.get("Customer Email") or "").strip()

        if mobile:
            new_cache[mobile] = row
        if email:
            new_cache[email.lower()] = row

    cache = new_cache
    last_updated = time.time()
    print("✅ Cache refreshed:", len(cache))


def get_cached_data():
    global last_updated

    if time.time() - last_updated > CACHE_TTL:
        refresh_cache()

    return cache


@app.route("/")
def home():
    return "API is running 🚀"


@app.route("/search", methods=["POST"])
def search():
    try:
        data = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip()

        if not query:
            return jsonify({"status": "Invalid query"})

        data_cache = get_cached_data()

        row = data_cache.get(query) or data_cache.get(query.lower())

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
        print("ERROR:", str(e))
        return jsonify({"status": "Error", "message": str(e)})


# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
