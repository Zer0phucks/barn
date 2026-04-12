import sys
from pathlib import Path
sys.path.insert(0, "/home/noob/barn/scan")
import db

bill = db.get_bill_with_parcel('53-1586-27')
print(list(bill.keys()))
