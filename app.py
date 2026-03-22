from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

sheet = client.open("YourSheetName").sheet1

@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query")

    records = sheet.get_all_records()

    for row in records:
        if str(row["Mobile"]) == query or str(row["Email"]) == query:
            return jsonify({"result": row["Status"]})

    return jsonify({"result": "Not Found"})

if __name__ == "__main__":
    app.run()