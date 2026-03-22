from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json


app = Flask(__name__)
CORS(app)
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]


client = gspread.authorize(creds)

# Open main sheet
spreadsheet = client.open("BOOK QUERIES")

# Open specific worksheet (IMPORTANT)
sheet = spreadsheet.worksheet("All order")

@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = str(data.get("query")).strip()

    records = sheet.get_all_records()

    for row in records:
        mobile = str(row.get("Customer Mobile", "")).strip()
        email = str(row.get("Customer Email", "")).strip()
        awb = str(row.get("AWB Code", "")).strip()
        status = str(row.get("Status", "")).strip()
        courier = str(row.get("Courier Company", "")).strip()

        if query == mobile or query == email:

            # Generate tracking link (Shiprocket default)
            tracking_link = f"https://shiprocket.co/tracking/{awb}"

            return jsonify({
                "status": status,
                "awb": awb,
                "courier": courier,
                "tracking_link": tracking_link
            })

    return jsonify({"status": "Not Found"})
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    
    