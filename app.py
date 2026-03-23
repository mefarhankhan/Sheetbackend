import os
import json
import gspread
from flask import Flask, request, jsonify
from flask_cors import CORS
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
CORS(app)

# ✅ REQUIRED: Google API scope
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# ✅ Load credentials from Render ENV variable
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# ✅ Authorize client
client = gspread.authorize(creds)

# ✅ Open your spreadsheet and worksheet
spreadsheet = client.open("BOOK QUERIES")
sheet = spreadsheet.worksheet("All order")


# ✅ API Route
@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = str(data.get("query", "")).strip()

    if not query:
        return jsonify({"status": "Please enter mobile or email"})

    try:
        records = sheet.get_all_records()

        for row in records:
            mobile = str(row.get("Customer Mobile", "")).strip()
            email = str(row.get("Customer Email", "")).strip()
            awb = str(row.get("AWB Code", "")).strip()
            status = str(row.get("Status", "")).strip()
            courier = str(row.get("Courier Company", "")).strip()

            # ✅ Match mobile or email
            if query == mobile or query.lower() == email.lower():

                # ✅ Handle missing AWB
                if not awb:
                    return jsonify({
                        "status": status,
                        "courier": courier,
                        "awb": "Not available",
                        "tracking_link": "Not available yet"
                    })

                # ✅ Generate tracking link (Shiprocket)
                tracking_link = f"https://shiprocket.co/tracking/{awb}"

                return jsonify({
                    "status": status,
                    "courier": courier,
                    "awb": awb,
                    "tracking_link": tracking_link
                })

        return jsonify({"status": "Not Found"})

    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)})


# ✅ Run app (Render compatible)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
