import sys
from pathlib import Path
sys.path.insert(0, "/home/noob/barn/scan")
import db

with open("/home/noob/barn/scan/delinquent_over_2_years_berkeley.txt", "r") as f:
    apn = f.readline().strip()

print(f"APN: {apn}")
bill = db.get_bill_with_parcel(apn)
for k, v in bill.items():
    print(f"{k}: {v}")
