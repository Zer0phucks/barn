#!/usr/bin/env python3
"""
Populate property_search_url and mailing_search_url for all bills.
Iterates through all bills, computes URLs based on parcel data, and updates the database.
"""
import asyncio
import json
import logging
import sys
from typing import Any

import db

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_address_parts_from_parcel(parcel: dict[str, Any]) -> dict[str, str]:
    """
    Extract street, city, zip from parcel data (Situs address).
    Replicates logic from contact_scanner.py but focused on parcel data.
    """
    street_number = parcel.get("SitusStreetNumber", "")
    street_name = parcel.get("SitusStreetName", "")
    situs_city = parcel.get("SitusCity", "")
    situs_zip = parcel.get("SitusZip", "")

    # Compose the street portion (e.g. "1 ROCHDALE WAY")
    if street_number and street_name:
        street_address = f"{street_number} {street_name}"
    elif parcel.get("SitusAddress"):
        # Fallback if components missing but full string exists
        # This part is a bit tricky, relying on components is safer for URL construction
        street_address = parcel["SitusAddress"]
    else:
        street_address = ""

    return {
        "street": street_address.strip(),
        "city": situs_city.strip(),
        "zip": situs_zip.strip(),
    }


def build_mailing_address_parts(parcel: dict[str, Any]) -> dict[str, str]:
    """
    Extract street, city, zip from parcel data (Mailing address).
    """
    street = parcel.get("MailingAddressStreet", "")
    city_state = parcel.get("MailingAddressCityState", "")
    zip_code = parcel.get("MailingAddressZip", "")

    city = ""
    if city_state:
        # Assume format "CITY STATE" e.g. "OAKLAND CA"
        parts = city_state.rsplit(" ", 1)
        if len(parts) > 0:
            city = parts[0]
    
    return {
        "street": street.strip(),
        "city": city.strip(),
        "zip": zip_code.strip(),
    }


def build_cyber_url(addr: dict[str, str]) -> str | None:
    """Build cyberbackgroundchecks.com address URL."""
    if not addr["street"] or not addr["zip"]:
        return None
        
    street_slug = addr["street"].replace(" ", "-")
    city_slug = addr["city"].replace(" ", "-") if addr["city"] else ""
    
    # If city is missing, the URL structure usually requires it.
    # We'll try our best.
    if not city_slug:
        return None

    return f"https://www.cyberbackgroundchecks.com/address/{street_slug}/{city_slug}/{addr['zip']}"


def main() -> None:
    logger.info("Starting population of search URLs...")

    page = 1
    page_size = 1000
    total_processed = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0

    while True:
        logger.info(f"Fetching batch: page={page}, page_size={page_size}")
        try:
            # Fetch batch of bills with parcel data
            # Returns (rows, total_count)
            batch, _ = db.get_bills_with_parcels_filtered(page=page, page_size=page_size)
            if not batch:
                break
            
            apns = [b["apn"] for b in batch if b.get("apn")]
            if not apns:
                continue

            # Fetch parcels for this batch
            try:
                parcel_res = db.get_client().table("parcels").select("APN, row_json").in_("APN", apns).execute()
                parcel_map = {row["APN"]: row.get("row_json") for row in (parcel_res.data or [])}
            except Exception as e:
                logger.error(f"Error fetching parcels for batch: {e}")
                parcel_map = {}

            for bill_data in batch:
                total_processed += 1
                apn = bill_data.get("apn")
                if not apn:
                    continue

                current_prop_url = bill_data.get("property_search_url")
                current_mail_url = bill_data.get("mailing_search_url")
                
                # Get parcel data from our map
                raw_json = parcel_map.get(apn)
                parcel_data = {}
                if isinstance(raw_json, dict):
                    parcel_data = raw_json
                elif isinstance(raw_json, str):
                    try:
                        parcel_data = json.loads(raw_json)
                    except json.JSONDecodeError:
                        parcel_data = {}
                
                updates = {}
                
                # Build Property URL
                prop_addr = build_address_parts_from_parcel(parcel_data)
                prop_url = build_cyber_url(prop_addr)
                
                # Build Mailing URL
                mail_addr = build_mailing_address_parts(parcel_data)
                mail_url = build_cyber_url(mail_addr)
                
                # Check updates
                if prop_url and prop_url != current_prop_url:
                    updates["property_search_url"] = prop_url
                
                if mail_url and mail_url != current_mail_url:
                    updates["mailing_search_url"] = mail_url
                
                if updates:
                    try:
                        # We need owner_contact_status to call update_bill_owner_contact
                        status = bill_data.get("owner_contact_status") or "null" # fallback if None?
                        db.update_bill_owner_contact(apn, status, **updates)
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"Error updating APN {apn}: {e}")
                        error_count += 1
                else:
                    if total_processed <= 5:
                        logger.info(f"DEBUG APN {apn}:")
                        logger.info(f"  Current Prop URL: {current_prop_url}")
                        logger.info(f"  New Prop URL: {prop_url}")
                        logger.info(f"  Current Mail URL: {current_mail_url}")
                        logger.info(f"  New Mail URL: {mail_url}")
                        logger.info(f"  Parcel Data: {parcel_data}")
                    skipped_count += 1
            
            page += 1
            
        except Exception as e:
            logger.error(f"Error fetching batch: {e}")
            break

    logger.info("Finished.")
    logger.info(f"Total Processed: {total_processed}")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Errors: {error_count}")


if __name__ == "__main__":
    main()
