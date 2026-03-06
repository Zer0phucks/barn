#!/usr/bin/env python3
"""
Merge PropertyRadar CSV export into Supabase database.
- Normalizes APNs by stripping leading zeros from each segment
- If property exists (by normalized APN): update only NULL/empty fields
- If property is new: insert into parcels and bills tables
- Also tries to match by address+city if APN doesn't match
"""

import csv
import re
import os
import sys
import json
from urllib.request import Request, urlopen
from urllib.parse import quote

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vzgmmlaojvkpbakvgcwh.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

CSV_PATH = "/home/noob/BARN-scan/propertyradar_export.csv"


def supabase_request(method, path, data=None, params=None):
    """Make a request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal" if method != "GET" else "",
    }
    
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    
    try:
        with urlopen(req) as resp:
            if resp.status in (200, 201):
                return json.loads(resp.read())
            return None
    except Exception as e:
        return None


def normalize_apn(apn):
    """
    Normalize APN by stripping leading zeros from each segment.
    e.g., '011-0862-029' -> '11-862-29'
    Also handles formats like '148-070-049-9' -> '148-70-49-9'
    """
    if not apn:
        return ''
    
    # Clean up OCR artifacts
    apn = apn.strip().strip("'\"")
    
    # Remove trailing '...' from OCR truncation
    apn = re.sub(r'\.+$', '', apn)
    
    # If it's truncated, we can't reliably use it
    if apn.endswith('..') or apn.endswith('.'):
        return ''
    
    # Split by common separators
    parts = re.split(r'[-]', apn)
    
    # Strip leading zeros from each part
    normalized_parts = []
    for part in parts:
        # Remove leading zeros but keep at least one digit
        stripped = part.lstrip('0') or '0'
        normalized_parts.append(stripped)
    
    return '-'.join(normalized_parts)


def extract_address_key(address_str):
    """Extract a normalized address key for matching."""
    if not address_str:
        return ''
    # Normalize: uppercase, strip extra spaces, remove common suffixes
    key = address_str.upper().strip()
    # Remove city suffix if present (e.g., "1234 MAIN ST, OAKLAND" -> "1234 MAIN ST")
    if ',' in key:
        key = key.split(',')[0].strip()
    # Remove dots
    key = key.replace('.', '')
    return key


def yesno_to_bool(val):
    """Convert Yes/No string to boolean."""
    if not val:
        return None
    v = val.strip().lower().strip("'\"")
    if v == 'yes':
        return True
    if v == 'no':
        return False
    return None


def main():
    global SUPABASE_KEY
    if not SUPABASE_KEY:
        # Read from .env file
        env_path = "/home/noob/BARN-scan/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and ('Service_Key' in line or 'SERVICE_ROLE' in line or 'SUPABASE_KEY' in line):
                        val = line.split('=', 1)[-1].strip().strip('"').strip("'")
                        if val and len(val) > 20:
                            SUPABASE_KEY = val
                            break
    
    if not SUPABASE_KEY:
        print("ERROR: No Supabase service key found!")
        sys.exit(1)
    
    print("=" * 60)
    print("Merge PropertyRadar CSV → Supabase")
    print(f"CSV: {CSV_PATH}")
    print("=" * 60)
    
    # Read CSV
    csv_rows = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)
    
    print(f"CSV rows: {len(csv_rows)}")
    
    # Load all existing bills from DB
    print("Loading existing properties from database...")
    # We need to use the Supabase SQL endpoint for this
    # Actually, let's use a Python approach with psycopg2 or the REST API
    
    # For REST API, we need to paginate
    all_bills = []
    offset = 0
    page_size = 1000
    while True:
        url = f"{SUPABASE_URL}/rest/v1/bills?select=apn,location_of_property,city,owner_name,zip_code,owner_occupied,site_vacant,deceased_owner,non_owner_occupied,mail_vacant&offset={offset}&limit={page_size}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        req = Request(url, headers=headers)
        try:
            with urlopen(req) as resp:
                page = json.loads(resp.read())
                if not page:
                    break
                all_bills.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
        except Exception as e:
            print(f"  Error fetching bills: {e}")
            break
    
    print(f"Existing DB records: {len(all_bills)}")
    
    # Build lookup maps
    # 1. By normalized APN
    apn_map = {}
    for bill in all_bills:
        norm = normalize_apn(bill['apn'])
        if norm:
            apn_map[norm] = bill
    
    # 2. By address key  
    addr_map = {}
    for bill in all_bills:
        if bill.get('location_of_property'):
            key = extract_address_key(bill['location_of_property'])
            if key:
                addr_map[key] = bill
    
    print(f"APN lookup entries: {len(apn_map)}")
    print(f"Address lookup entries: {len(addr_map)}")
    
    # Process CSV rows
    updates = 0
    inserts = 0
    skipped = 0
    errors = 0
    
    for i, row in enumerate(csv_rows):
        if i % 100 == 0:
            sys.stdout.write(f"\r  Processing: {i}/{len(csv_rows)} (upd:{updates}, ins:{inserts}, skip:{skipped})")
            sys.stdout.flush()
        
        csv_apn = row.get('APN', '').strip().strip("'\"")
        csv_addr = row.get('Address', '').strip()
        csv_city = row.get('City', '').strip()
        csv_owner = row.get('Owner', '').strip()
        csv_zip = row.get('Zip', '').strip().strip("'\"")
        
        owner_occ = yesno_to_bool(row.get('Owner Occ?', ''))
        site_vacant = yesno_to_bool(row.get('Site Vacant?', ''))
        deceased_owner = yesno_to_bool(row.get('Deceased Owner?', ''))
        non_owner_occ = yesno_to_bool(row.get('Non-Owner Occ?', ''))
        mail_vacant = yesno_to_bool(row.get('Mail Vacant?', ''))
        
        norm_apn = normalize_apn(csv_apn)
        addr_key = extract_address_key(csv_addr)
        
        # Try to find existing record
        existing = None
        match_apn = None
        
        # First try APN match
        if norm_apn and norm_apn in apn_map:
            existing = apn_map[norm_apn]
            match_apn = existing['apn']
        
        # Then try address match
        if not existing and addr_key:
            if addr_key in addr_map:
                existing = addr_map[addr_key]
                match_apn = existing['apn']
            else:
                # Try with city appended
                full_key = f"{addr_key}, {csv_city}".upper() if csv_city else addr_key
                if full_key in addr_map:
                    existing = addr_map[full_key]
                    match_apn = existing['apn']
        
        if existing:
            # UPDATE existing record - only fill in NULL/empty fields
            update_data = {}
            
            if not existing.get('owner_name') and csv_owner and '...' not in csv_owner:
                update_data['owner_name'] = csv_owner
            
            if not existing.get('zip_code') and csv_zip and len(csv_zip) == 5:
                update_data['zip_code'] = csv_zip
            
            if not existing.get('location_of_property') and csv_addr:
                loc = f"{csv_addr}, {csv_city}" if csv_city else csv_addr
                update_data['location_of_property'] = loc
            
            if not existing.get('city') and csv_city:
                update_data['city'] = csv_city
            
            if existing.get('owner_occupied') is None and owner_occ is not None:
                update_data['owner_occupied'] = owner_occ
            
            if existing.get('site_vacant') is None and site_vacant is not None:
                update_data['site_vacant'] = site_vacant
            
            if existing.get('deceased_owner') is None and deceased_owner is not None:
                update_data['deceased_owner'] = deceased_owner
            
            if existing.get('non_owner_occupied') is None and non_owner_occ is not None:
                update_data['non_owner_occupied'] = non_owner_occ
            
            if existing.get('mail_vacant') is None and mail_vacant is not None:
                update_data['mail_vacant'] = mail_vacant
            
            if update_data:
                # Do the update via REST API
                url = f"{SUPABASE_URL}/rest/v1/bills?apn=eq.{quote(match_apn)}"
                headers = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                }
                body = json.dumps(update_data).encode()
                req = Request(url, data=body, headers=headers, method="PATCH")
                try:
                    with urlopen(req) as resp:
                        updates += 1
                except Exception as e:
                    errors += 1
            else:
                skipped += 1
        else:
            # INSERT new record
            # Skip if APN is truncated/invalid
            if not norm_apn or len(norm_apn) < 4:
                if not csv_addr or len(csv_addr) < 3:
                    skipped += 1
                    continue
                # Use address as a fallback APN key
                norm_apn = f"PR-{csv_addr[:30].replace(' ', '-').replace(',', '')}"
            
            # Use the original CSV APN format for the DB
            db_apn = norm_apn
            
            location = f"{csv_addr}, {csv_city}" if csv_city else csv_addr
            
            # First insert into parcels
            parcel_data = {
                "APN": db_apn,
            }
            url = f"{SUPABASE_URL}/rest/v1/parcels"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal,resolution=ignore-duplicates",
            }
            body = json.dumps(parcel_data).encode()
            req = Request(url, data=body, headers=headers, method="POST")
            try:
                with urlopen(req) as resp:
                    pass
            except Exception as e:
                # Parcel might already exist (conflict), that's ok
                pass
            
            # Then insert into bills
            bill_data = {
                "apn": db_apn,
                "location_of_property": location if csv_addr else None,
                "city": csv_city if csv_city else None,
                "owner_name": csv_owner if csv_owner and '...' not in csv_owner else None,
                "zip_code": csv_zip if csv_zip and len(csv_zip) == 5 else None,
                "owner_occupied": owner_occ,
                "site_vacant": site_vacant,
                "deceased_owner": deceased_owner,
                "non_owner_occupied": non_owner_occ,
                "mail_vacant": mail_vacant,
                "has_vpt": 0,
            }
            # Remove None values
            bill_data = {k: v for k, v in bill_data.items() if v is not None}
            
            url = f"{SUPABASE_URL}/rest/v1/bills"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            body = json.dumps(bill_data).encode()
            req = Request(url, data=body, headers=headers, method="POST")
            try:
                with urlopen(req) as resp:
                    inserts += 1
            except Exception as e:
                err_msg = str(e)
                if '409' in err_msg or 'duplicate' in err_msg.lower() or '23505' in err_msg:
                    skipped += 1
                else:
                    errors += 1
                    if errors <= 5:
                        print(f"\n  Insert error for APN {db_apn}: {e}")
    
    print(f"\n\n{'='*60}")
    print(f"Results:")
    print(f"  Updated: {updates}")
    print(f"  Inserted: {inserts}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"{'='*60}")
    
    # Final count
    url = f"{SUPABASE_URL}/rest/v1/bills?select=count"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            count_header = resp.getheader('content-range')
            print(f"  Total DB records now: {count_header}")
    except:
        pass
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
