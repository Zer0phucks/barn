#!/usr/bin/env python3
"""
PropertyRadar PDF → CSV - V8 (Parallel + Optimized)
Uses multiprocessing to parallelize OCR across pages.
Reduced scale and DPI for speed while maintaining quality.
"""

import subprocess
import os
import csv
import re
import sys
import multiprocessing
from PIL import Image
import pytesseract

PDF_PATH = "/home/noob/BARN-scan/screencapture-app-propertyradar-2026-02-25-15_26_00.pdf"
OUTPUT_CSV = "/home/noob/BARN-scan/propertyradar_export.csv"
TEMP_DIR = "/tmp/propertyradar_v8"
TOTAL_PAGES = 58
DPI = 250
SCALE = 2
NUM_WORKERS = 4

HEADERS = [
    "Address", "City", "Owner", "Owner Occ?", "Site Vacant?",
    "Deceased Owner?", "APN", "Zip", "Non-Owner Occ?", "Mail Vacant?"
]

KEY_COLS = [
    ('Address',  0.055, 0.143),
    ('City',     0.143, 0.200),
    ('Owner',    0.200, 0.280),
    ('APN',      0.425, 0.472),
    ('Zip',      0.472, 0.525),
]

YESNO_COLS = [
    ('Owner Occ?',      0.278, 0.328),
    ('Site Vacant?',     0.328, 0.383),
    ('Deceased Owner?',  0.383, 0.425),
    ('Non-Owner Occ?',   0.525, 0.575),
    ('Mail Vacant?',     0.575, 0.640),
]

TOP_SKIP_PCT = 0.055


def normalize_yesno(text):
    t = text.strip().lower()
    if not t: return ''
    yes_set = {'yes', 'ye', 'ves', 'yee', 'se', 'te', 've', 'es', 'vee', 'yer', 'yea'}
    no_set = {'no', 'wo', 'ne', 'so', 'ho', '%0', 'mo', 'n0', 'io', 'to', 'nc', 'na'}
    if t in yes_set: return 'Yes'
    if t in no_set: return 'No'
    if t.startswith('yes'): return 'Yes'
    if t.startswith('no'): return 'No'
    return text.strip()


def ocr_strip(img, x_start_pct, x_end_pct, top_skip_pct, col_name):
    """OCR a column strip, return list of (y_pos, text)."""
    W, H = img.size
    left = int(W * x_start_pct)
    right = int(W * x_end_pct)
    top = int(H * top_skip_pct)
    
    strip = img.crop((left, top, right, H))
    sw, sh = strip.size
    scaled = strip.resize((sw * SCALE, sh * SCALE), Image.LANCZOS)
    
    config = '--psm 4'
    if col_name == 'Zip':
        config = '--psm 4 -c tessedit_char_whitelist=0123456789'
    
    data = pytesseract.image_to_data(scaled, config=config, output_type=pytesseract.Output.DICT)
    
    words = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if not text: continue
        if int(data['conf'][i]) < 0: continue
        words.append({'text': text, 'top': data['top'][i], 'left': data['left'][i]})
    
    if not words:
        return []
    
    words.sort(key=lambda w: w['top'])
    lines = []
    cur = [words[0]]
    cur_y = words[0]['top']
    
    for w in words[1:]:
        if abs(w['top'] - cur_y) < (16 * SCALE):
            cur.append(w)
        else:
            cur.sort(key=lambda w: w['left'])
            text = ' '.join(w['text'] for w in cur)
            avg_y = sum(w['top'] for w in cur) / len(cur)
            orig_y = avg_y / SCALE + (H * top_skip_pct)
            lines.append((orig_y, text))
            cur = [w]
            cur_y = w['top']
    
    if cur:
        cur.sort(key=lambda w: w['left'])
        text = ' '.join(w['text'] for w in cur)
        avg_y = sum(w['top'] for w in cur) / len(cur)
        orig_y = avg_y / SCALE + (H * top_skip_pct)
        lines.append((orig_y, text))
    
    return lines


def ocr_yesno_strip(img, yesno_cols, top_skip_pct):
    """OCR the combined Yes/No area."""
    W, H = img.size
    left = int(W * min(c[1] for c in yesno_cols))
    right = int(W * max(c[2] for c in yesno_cols))
    top = int(H * top_skip_pct)
    
    strip = img.crop((left, top, right, H))
    strip_w = right - left
    sw, sh = strip.size
    scaled = strip.resize((sw * SCALE, sh * SCALE), Image.LANCZOS)
    
    data = pytesseract.image_to_data(scaled, config='--psm 6', output_type=pytesseract.Output.DICT)
    
    col_data = {c[0]: [] for c in yesno_cols}
    min_x = min(c[1] for c in yesno_cols)
    max_x = max(c[2] for c in yesno_cols)
    span = max_x - min_x
    
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if not text: continue
        if int(data['conf'][i]) < 0: continue
        
        wc_pct = (data['left'][i] + data['width'][i] / 2) / (strip_w * SCALE)
        word_x = min_x + wc_pct * span
        orig_y = data['top'][i] / SCALE + (H * top_skip_pct)
        
        for col_name, cs, ce in yesno_cols:
            if cs <= word_x < ce:
                val = normalize_yesno(text)
                if val:
                    col_data[col_name].append((orig_y, val))
                break
    
    return col_data


def process_page(page_num):
    """Process one page. Returns (page_num, rows)."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    prefix = os.path.join(TEMP_DIR, f"p{page_num:02d}")
    
    subprocess.run(
        ["pdftoppm", "-f", str(page_num), "-l", str(page_num),
         "-png", "-r", str(DPI), PDF_PATH, prefix],
        capture_output=True, text=True
    )
    
    img_path = None
    for f in os.listdir(TEMP_DIR):
        if f.startswith(f"p{page_num:02d}") and f.endswith('.png'):
            img_path = os.path.join(TEMP_DIR, f)
            break
    
    if not img_path:
        return (page_num, [])
    
    img = Image.open(img_path)
    
    # OCR key columns
    key_data = {}
    for col_name, xs, xe in KEY_COLS:
        key_data[col_name] = ocr_strip(img, xs, xe, TOP_SKIP_PCT, col_name)
    
    # OCR Yes/No columns
    yn_data = ocr_yesno_strip(img, YESNO_COLS, TOP_SKIP_PCT)
    
    os.remove(img_path)
    
    # Align using Address Y positions
    addr_lines = key_data.get('Address', [])
    tolerance = 10
    
    rows = []
    for addr_y, addr_text in addr_lines:
        if addr_text.lower() in ('address', 'type', 'actions'):
            continue
        if not any(c.isdigit() for c in addr_text) or len(addr_text) < 3:
            continue
        
        row = [addr_text]
        
        # Match other key columns
        for col_name in ['City', 'Owner', 'APN', 'Zip']:
            best = ''
            best_d = float('inf')
            for y, t in key_data.get(col_name, []):
                d = abs(y - addr_y)
                if d < best_d and d < tolerance:
                    best_d = d
                    best = t
            row.append(best)
        
        # Insert Yes/No columns in the right positions
        # Row order: Address, City, Owner, OwnerOcc, SiteVac, Deceased, APN, Zip, NonOwner, MailVac
        yn_vals = {}
        for col_name in ['Owner Occ?', 'Site Vacant?', 'Deceased Owner?', 'Non-Owner Occ?', 'Mail Vacant?']:
            best = ''
            best_d = float('inf')
            for y, t in yn_data.get(col_name, []):
                d = abs(y - addr_y)
                if d < best_d and d < tolerance:
                    best_d = d
                    best = t
            yn_vals[col_name] = best
        
        # Reconstruct in HEADERS order:
        # Address(0), City(1), Owner(2), OwnerOcc(3), SiteVac(4), Deceased(5), APN(6), Zip(7), NonOwner(8), MailVac(9)
        final_row = [
            row[0],                        # Address
            row[1].strip("'\""),            # City
            row[2].strip("'\""),            # Owner
            yn_vals['Owner Occ?'],
            yn_vals['Site Vacant?'],
            yn_vals['Deceased Owner?'],
            row[3].strip("'\""),            # APN
            row[4].strip("'\""),            # Zip
            yn_vals['Non-Owner Occ?'],
            yn_vals['Mail Vacant?'],
        ]
        rows.append(final_row)
    
    return (page_num, rows)


def main():
    print("=" * 60)
    print("PropertyRadar PDF → CSV (v8 - Parallel)")
    print(f"PDF: {PDF_PATH}")
    print(f"Output: {OUTPUT_CSV}")
    print(f"Pages: {TOTAL_PAGES}, DPI: {DPI}, Workers: {NUM_WORKERS}")
    print("=" * 60)
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Process pages in parallel
    all_results = {}
    with multiprocessing.Pool(NUM_WORKERS) as pool:
        futures = []
        for pn in range(1, TOTAL_PAGES + 1):
            futures.append(pool.apply_async(process_page, (pn,)))
        
        for i, fut in enumerate(futures):
            result = fut.get()
            pn, rows = result
            all_results[pn] = rows
            sys.stdout.write(f"\r  Completed: {i+1}/{TOTAL_PAGES} pages ({len(rows)} rows from page {pn})")
            sys.stdout.flush()
    
    # Combine in page order
    all_rows = []
    for pn in range(1, TOTAL_PAGES + 1):
        all_rows.extend(all_results.get(pn, []))
    
    print(f"\n  Raw: {len(all_rows)} rows")
    
    # Dedup
    seen = set()
    unique = []
    for row in all_rows:
        apn = row[6].strip()
        addr = row[0].strip()
        key = apn if apn else addr
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(row)
    
    print(f"  Unique: {len(unique)} rows")
    
    # Write CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for row in unique:
            writer.writerow(row[:len(HEADERS)])
    
    print(f"\n✅ CSV: {OUTPUT_CSV}")
    print(f"   {len(unique)} data rows")
    
    # Preview
    print(f"\n{'─'*145}")
    print(f"{'Address':<28} {'City':<17} {'Owner':<28} {'OO':<5} {'SV':<5} {'DO':<5} {'APN':<18} {'Zip':<7} {'NO':<5} {'MV':<5}")
    print(f"{'─'*145}")
    for row in unique[:25]:
        r = row + ['']*(10-len(row))
        print(f"{r[0][:27]:<28} {r[1][:16]:<17} {r[2][:27]:<28} {r[3]:<5} {r[4]:<5} {r[5]:<5} {r[6][:17]:<18} {r[7]:<7} {r[8]:<5} {r[9]:<5}")
    if len(unique) > 25:
        print(f"  ... +{len(unique)-25} more")
    
    # Cleanup
    import shutil
    try:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    except:
        pass
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
