import sys
from pathlib import Path
sys.path.insert(0, "/home/noob/barn/scan")
import db

unresearched_apns = []
unpowered_apns = []

with open("/home/noob/barn/scan/delinquent_over_2_years_berkeley.txt", "r") as f:
    apns = [line.strip() for line in f if line.strip()]

for apn in apns:
    bill = db.get_bill_with_parcel(apn)
    if bill.get('research_status') != 'completed':
        unresearched_apns.append(apn)
    if not bill.get('power_status'):
        unpowered_apns.append(apn)

print(f"Total: {len(apns)}")
print(f"Unresearched: {len(unresearched_apns)}")
print(f"No power_status: {len(unpowered_apns)}")
