"""Load a bills-export CSV (same columns as the bills table) into Supabase.

Existing APNs are left untouched (ignore_duplicates), so re-running is safe.
Run scripts/geocode_bills.py afterwards so the rows appear in map_markers.

    python scripts/import_bills_csv.py path/to/export.csv
"""
import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
import db  # noqa: E402

if len(sys.argv) != 2:
    sys.exit("usage: import_bills_csv.py path/to/export.csv")
CSV_PATH = sys.argv[1]
INT_COLS = {"has_vpt", "delinquent", "deceased_count"}
FLOAT_COLS = {"condition_score"}
BOOL_COLS = {"tenant_verified"}
SKIP_COLS = {"situs_zip"}  # not a bills column; empty in this file anyway


def convert(col, val):
    val = (val or "").strip()
    if val == "" or val.lower() == "null":
        return None
    if col in INT_COLS:
        return int(float(val))
    if col in FLOAT_COLS:
        return float(val)
    if col in BOOL_COLS:
        return val.lower() in ("1", "true", "t", "yes")
    return val


rows = []
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        payload = {k: convert(k, v) for k, v in r.items() if k not in SKIP_COLS}
        payload = {k: v for k, v in payload.items() if v is not None}
        payload.setdefault("has_vpt", 0)
        payload.setdefault("delinquent", 0)
        payload.setdefault("pdf_file", "")
        rows.append(payload)

client = db.get_client()
BATCH = 100
for i in range(0, len(rows), BATCH):
    chunk = rows[i : i + BATCH]
    # PostgREST bulk insert needs identical keys per row.
    keys = set().union(*chunk)
    chunk = [{k: r.get(k) for k in keys} for r in chunk]
    for r in chunk:
        for k, default in (("has_vpt", 0), ("delinquent", 0), ("pdf_file", "")):
            if r[k] is None:
                r[k] = default
        if r.get("added_at") is None:
            r["added_at"] = datetime.now(timezone.utc).isoformat()
    client.table("bills").upsert(chunk, on_conflict="apn", ignore_duplicates=True).execute()
    print(f"sent {i + len(chunk)}/{len(rows)}")

total = client.table("bills").select("apn", count="exact").limit(1).execute().count
print("bills rows now:", total)
