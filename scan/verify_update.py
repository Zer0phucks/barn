
import db
import json

apn = "48A-7076-10"
bill = db.get_bill(apn)
print(json.dumps(bill, indent=2))
