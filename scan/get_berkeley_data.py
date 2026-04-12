import sys
import json
from pathlib import Path

# Fix relative imports
sys.path.insert(0, "/home/noob/barn/scan")
import db

report_lines = []
report_lines.append("# Berkeley Delinquent Property Report")
report_lines.append("")
report_lines.append("This report contains additional information extracted from the Alameda County tax records and the local BARN property database.")
report_lines.append("")

with open("/home/noob/barn/scan/delinquent_over_2_years_berkeley.txt", "r") as f:
    apns = [line.strip() for line in f if line.strip()]

for apn in apns:
    bill = db.get_bill_with_parcel(apn)
    if not bill:
        continue
    
    loc = bill.get("location_of_property") or "Unknown Address"
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        try:
            row_json = json.loads(row_json)
        except:
            row_json = {}
            
    mailing = row_json.get("MailingAddress") or ""
    last_sale = row_json.get("LatestDocumentDate") or "Unknown"
    power = bill.get("power_status") or "Unknown"
    resident = bill.get("primary_resident_name") or "Unknown (Requires AI Research)"
    
    mailing_diff = "Same as property"
    if mailing and loc and (" ".join(mailing.lower().split()[:2]) not in loc.lower()):
        mailing_diff = mailing
        
    power_icon = "⚪"
    if power == "on": power_icon = "🟢 On"
    elif power == "off": power_icon = "🔴 Off"
    
    report_lines.append(f"### {loc} (APN: {apn})")
    report_lines.append(f"- **Current Resident:** {resident}")
    report_lines.append(f"- **Mailing Address:** {mailing_diff}")
    report_lines.append(f"- **Last Sale Date:** {last_sale}")
    report_lines.append(f"- **PG&E Power Status:** {power_icon}")
    report_lines.append(f"- **Water Status:** Not tracked by Alameda County records\n")

with open("berkeley_data.md", "w") as f:
    f.write("\n".join(report_lines))
    
print("Done writing to berkeley_data.md")
