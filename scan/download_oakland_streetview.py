import os
import sys
import time
from pathlib import Path

# Need to be able to import condition_scanner and db
scan_dir = Path("/home/noob/barn/scan")
sys.path.insert(0, str(scan_dir))

import condition_scanner
import db

import asyncio

async def main():
    oakland_file = scan_dir / "delinquent_over_2_years.txt"
    with open(oakland_file, "r") as f:
        apns = [line.strip() for line in f if line.strip()]
        
    print(f"Loaded {len(apns)} APNs from {oakland_file.name}")
    
    count = 0
    missing = 0
    for apn in apns:
        safe_apn = apn.replace("/", "_").replace("\\", "_")
        image_path = scan_dir / "streetview_images" / f"{safe_apn}.jpg"
        
        if image_path.exists() and image_path.stat().st_size > 1000:
            print(f"Skipping {apn}, already exists and >1kb")
            continue
            
        coords = condition_scanner.get_property_coords(apn)
        if not coords:
            print(f"Could not get coords for {apn}")
            missing += 1
            continue
            
        lat, lng = coords
        print(f"Fetching {apn} at {lat}, {lng}")
        result = await condition_scanner.fetch_streetview_image(lat, lng, apn)
        if result:
            count += 1
            print(f"  Saved to {result}")
        else:
            print(f"  Failed for {apn}")
            missing += 1
            
    print(f"Done! Downloaded {count} new images. Missing/failed: {missing}")

    # Re-generate the dashboard so it picks up the new images!
    import generate_dashboard
    generate_dashboard.generate("OAKLAND")

if __name__ == "__main__":
    asyncio.run(main())
