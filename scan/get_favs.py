import sys
import json
import os
sys.path.append("/home/noob/BARN-scan")

# load environment variables from .env
from dotenv import load_dotenv
load_dotenv("/home/noob/BARN-scan/.env")

from webgui import db_impl
apns = db_impl.get_favorites_apns()
print(f"Found {len(apns)} favorites")
fav_data = []
for apn in apns:
    bill = db_impl.get_bill_with_parcel(apn)
    if bill and bill.get("row_json"):
        import json
        try:
            row_data = bill["row_json"]
            if isinstance(row_data, str):
                row_data = json.loads(row_data)
        except Exception:
            row_data = {}
        address = row_data.get("SitusAddress", "")
        city = row_data.get("SitusCity", "")
        owner = "UNKNOWN"
        fav_data.append({
            "apn": apn,
            "address": address,
            "city": city,
            "owner": owner
        })
    else:
        fav_data.append({"apn": apn, "address": "UNKNOWN", "city": "UNKNOWN", "owner": "UNKNOWN"})
with open("/home/noob/BARN-scan/favs.json", "w") as f:
    json.dump(fav_data, f, indent=2)
