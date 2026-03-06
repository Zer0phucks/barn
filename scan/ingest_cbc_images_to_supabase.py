#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError as exc:
    raise RuntimeError("google-genai is required. Install with: pip install google-genai") from exc

try:
    from supabase import create_client
except ImportError as exc:
    raise RuntimeError("supabase is required. Install with: pip install supabase") from exc


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
INFO_FOUND_FILENAME_RE = re.compile(r"info found for\s*(.+)$", re.IGNORECASE)

ADDRESS_REPLACEMENTS = {
    " STREET ": " ST ",
    " AVENUE ": " AVE ",
    " BOULEVARD ": " BLVD ",
    " ROAD ": " RD ",
    " DRIVE ": " DR ",
    " LANE ": " LN ",
    " COURT ": " CT ",
    " PLACE ": " PL ",
    " TERRACE ": " TER ",
    " CIRCLE ": " CIR ",
    " PARKWAY ": " PKWY ",
    " HIGHWAY ": " HWY ",
}

STREET_SUFFIXES = {
    "ST", "AVE", "BLVD", "RD", "DR", "LN", "CT", "PL", "TER", "CIR", "PKWY", "HWY",
    "WAY", "TRL", "PLZ", "ALY", "LOOP", "SQ",
}

DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}

STATE_TOKENS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "CALIFORNIA",
}


def load_env() -> None:
    repo_env = Path(__file__).resolve().parent / ".env"
    if repo_env.exists():
        load_dotenv(repo_env)
    else:
        load_dotenv()


def get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "(or SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY)."
        )
    return create_client(supabase_url, supabase_key)


def get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY in environment.")
    return genai.Client(api_key=api_key)


def _extract_json_block(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {}
    return {}


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        if v.lower() in {"n/a", "na", "null", "none", "unknown", "not available"}:
            return None
        return v
    return value


def normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "property_address": _clean_value(data.get("property_address")),
        "occupancy_type": _clean_value(data.get("occupancy_type")),
        "ownership_type": _clean_value(data.get("ownership_type")),
        "last_sale_date": _clean_value(data.get("last_sale_date")),
        "primary_resident_name": _clean_value(data.get("primary_resident_name")),
        "primary_resident_age": _clean_value(data.get("primary_resident_age")),
        "primary_resident_phone_number": _clean_value(data.get("primary_resident_phone_number")),
        "deceased_count": data.get("deceased_count"),
        "important_notes": _clean_value(data.get("important_notes")),
    }

    if normalized["deceased_count"] is None:
        normalized["deceased_count"] = None
    else:
        try:
            normalized["deceased_count"] = int(normalized["deceased_count"])
        except (TypeError, ValueError):
            normalized["deceased_count"] = None

    return normalized


def build_prompt() -> str:
    return (
        "You are extracting structured data from a property-related screenshot.\n"
        "Return ONLY valid JSON. No markdown.\n"
        "Use this exact schema:\n"
        "{\n"
        '  "property_address": string|null,\n'
        '  "occupancy_type": string|null,\n'
        '  "ownership_type": string|null,\n'
        '  "last_sale_date": string|null,\n'
        '  "primary_resident_name": string|null,\n'
        '  "primary_resident_age": string|null,\n'
        '  "primary_resident_phone_number": string|null,\n'
        '  "deceased_count": integer|null,\n'
        '  "important_notes": string|null\n'
        "}\n"
        "Rules:\n"
        "1) Extract the property address shown in the image into property_address.\n"
        "2) Primary resident is the FIRST name listed in the screenshot.\n"
        "3) If no deceased marker is present for any name, set deceased_count to null.\n"
        "4) If a field is not shown, use null.\n"
        "5) Do not guess values not present in the image."
    )


def extract_from_image(gemini_client, model: str, image_path: Path) -> tuple[dict[str, Any], str]:
    ext = image_path.suffix.lower()
    mime_type = "image/jpeg"
    if ext == ".png":
        mime_type = "image/png"
    elif ext == ".webp":
        mime_type = "image/webp"
    elif ext == ".bmp":
        mime_type = "image/bmp"
    elif ext in {".tif", ".tiff"}:
        mime_type = "image/tiff"

    image_bytes = image_path.read_bytes()
    prompt = build_prompt()

    response = gemini_client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
    )
    text = getattr(response, "text", "") or ""
    parsed = _extract_json_block(text)
    return normalize_extraction(parsed), text


def list_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")
    if not image_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {image_dir}")
    return sorted([p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])


def extract_address_from_filename(image_path: Path) -> str:
    stem = image_path.stem.strip()
    if not stem:
        return ""
    match = INFO_FOUND_FILENAME_RE.search(stem)
    if match:
        return match.group(1).strip()
    return stem


def _tokenize_address(raw: str | None) -> list[str]:
    if not raw:
        return []
    s = raw.upper()
    s = re.sub(r"\b(APT|UNIT|STE|SUITE)\b\s*[A-Z0-9-]*", " ", s)
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    padded = f" {s} "
    for long_form, short_form in ADDRESS_REPLACEMENTS.items():
        padded = padded.replace(long_form, short_form)
    normalized = re.sub(r"\s+", " ", padded).strip()
    tokens = normalized.split(" ")
    cleaned: list[str] = []
    for idx, token in enumerate(tokens):
        if not token:
            continue
        # Keep first token as potential house number even if it is 5 digits.
        if idx > 0 and re.fullmatch(r"\d{5}(?:\d{4})?", token):
            continue
        if token in STATE_TOKENS:
            continue
        cleaned.append(token)
    return cleaned


def normalize_address(raw: str | None) -> str:
    return " ".join(_tokenize_address(raw))


def get_street_key(raw: str | None) -> str:
    tokens = _tokenize_address(raw)
    if not tokens:
        return ""
    for i in range(1, len(tokens)):
        token = tokens[i]
        if token in STREET_SUFFIXES:
            end = i
            if i + 1 < len(tokens) and tokens[i + 1] in DIRECTIONALS:
                end = i + 1
            return " ".join(tokens[: end + 1])
    if len(tokens) >= 4:
        return " ".join(tokens[:4])
    return " ".join(tokens)


def get_city_key(raw: str | None) -> str:
    tokens = _tokenize_address(raw)
    if not tokens:
        return ""
    street_tokens = get_street_key(raw).split(" ")
    if not street_tokens:
        return ""
    if tokens[: len(street_tokens)] == street_tokens:
        remainder = tokens[len(street_tokens) :]
        return " ".join(remainder).strip()
    return ""


def _extract_house_number(street_key: str) -> str:
    first = street_key.split(" ")[0] if street_key else ""
    return first if first.isdigit() else ""


def fetch_bills_address_index(supabase) -> dict[str, dict[str, list[dict[str, str]]]]:
    full_index: dict[str, list[dict[str, str]]] = {}
    street_index: dict[str, list[dict[str, str]]] = {}
    house_number_index: dict[str, list[dict[str, str]]] = {}
    page_size = 1000
    start = 0

    while True:
        end = start + page_size - 1
        resp = (
            supabase.table("bills")
            .select("apn, location_of_property")
            .range(start, end)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        for row in rows:
            apn = (row.get("apn") or "").strip()
            addr = (row.get("location_of_property") or "").strip()
            full_key = normalize_address(addr)
            street_key = get_street_key(addr)
            city_key = get_city_key(addr)
            if not apn or not full_key:
                continue
            entry = {
                "apn": apn,
                "location_of_property": addr,
                "full_key": full_key,
                "street_key": street_key,
                "city_key": city_key,
            }
            full_index.setdefault(full_key, []).append(entry)
            if street_key:
                street_index.setdefault(street_key, []).append(entry)
                house_number = _extract_house_number(street_key)
                if house_number:
                    house_number_index.setdefault(house_number, []).append(entry)
        if len(rows) < page_size:
            break
        start += page_size

    return {"full": full_index, "street": street_index, "house_number": house_number_index}


def _resolve_candidate(
    candidates: list[dict[str, str]],
    extracted_city_key: str,
    base_status: str,
) -> tuple[str | None, str]:
    if len(candidates) == 1:
        return candidates[0]["apn"], base_status

    if extracted_city_key:
        city_exact = [c for c in candidates if c.get("city_key") == extracted_city_key]
        if len(city_exact) == 1:
            return city_exact[0]["apn"], f"{base_status}_city_exact"

        candidate_cities = sorted({c.get("city_key", "") for c in candidates if c.get("city_key")})
        if candidate_cities:
            fuzzy = difflib.get_close_matches(extracted_city_key, candidate_cities, n=1, cutoff=0.75)
            if fuzzy:
                city_fuzzy = [c for c in candidates if c.get("city_key") == fuzzy[0]]
                if len(city_fuzzy) == 1:
                    return city_fuzzy[0]["apn"], f"{base_status}_city_fuzzy"

    return None, f"{base_status}_ambiguous"


def match_bill_by_address(
    extracted_address: str | None,
    address_index: dict[str, dict[str, list[dict[str, str]]]],
) -> tuple[str | None, str]:
    full_key = normalize_address(extracted_address)
    street_key = get_street_key(extracted_address)
    extracted_city_key = get_city_key(extracted_address)

    if not full_key and not street_key:
        return None, "no_address_extracted"

    full_matches = address_index["full"].get(full_key, []) if full_key else []
    if full_matches:
        return _resolve_candidate(full_matches, extracted_city_key, "full")

    street_matches = address_index["street"].get(street_key, []) if street_key else []
    if street_matches:
        return _resolve_candidate(street_matches, extracted_city_key, "street")

    # OCR fallback: same house number, fuzzy street text.
    house_number = _extract_house_number(street_key)
    candidate_pool = address_index["house_number"].get(house_number, []) if house_number else []
    if street_key and candidate_pool:
        scored: list[tuple[float, dict[str, str]]] = []
        for candidate in candidate_pool:
            ratio = difflib.SequenceMatcher(None, street_key, candidate.get("street_key", "")).ratio()
            scored.append((ratio, candidate))
        scored.sort(key=lambda x: x[0], reverse=True)
        best_ratio = scored[0][0]
        if best_ratio >= 0.86:
            near_best = [c for ratio, c in scored if ratio >= best_ratio - 0.02]
            return _resolve_candidate(near_best, extracted_city_key, "street_fuzzy")

    return None, "not_found"


def ingest_images(
    image_dir: Path,
    audit_table: str | None,
    model: str,
    dry_run: bool,
) -> None:
    supabase = get_supabase_client()
    gemini_client = get_gemini_client()
    address_index = fetch_bills_address_index(supabase)

    images = list_images(image_dir)
    if not images:
        print(f"No images found in {image_dir}")
        return

    print(f"Found {len(images)} images in {image_dir}")
    print(
        "Loaded "
        f"{len(address_index['full'])} unique full addresses and "
        f"{len(address_index['street'])} unique street keys from bills table"
    )

    updated = 0
    failed = 0
    deleted = 0
    unmatched = 0

    for idx, image_path in enumerate(images, start=1):
        print(f"[{idx}/{len(images)}] Processing {image_path.name}")
        try:
            extracted, raw_response = extract_from_image(gemini_client, model, image_path)
            matched_apn, match_status = match_bill_by_address(extracted["property_address"], address_index)
            matched_address_source = "gemini"

            if not matched_apn:
                filename_address = extract_address_from_filename(image_path)
                if filename_address:
                    fallback_apn, fallback_status = match_bill_by_address(filename_address, address_index)
                    if fallback_apn:
                        matched_apn = fallback_apn
                        match_status = f"filename_{fallback_status}"
                        matched_address_source = "filename"
                        if not extracted.get("property_address"):
                            extracted["property_address"] = filename_address
                        print(f"  Fallback match from filename address -> APN {matched_apn}")

            if not matched_apn:
                unmatched += 1
                print(
                    f"  No unique property match ({match_status}). "
                    f"Extracted address: {extracted.get('property_address') or 'None'}"
                )
                continue

            bill_update = {
                "prop_occupancy_type": extracted["occupancy_type"],
                "prop_ownership_type": extracted["ownership_type"],
                "prop_last_sale_date": extracted["last_sale_date"],
                "owner_mobile_phone": extracted["primary_resident_phone_number"],
                "primary_resident_name": extracted["primary_resident_name"],
                "primary_resident_age": extracted["primary_resident_age"],
                "deceased_count": extracted["deceased_count"],
                "important_notes": extracted["important_notes"],
                "owner_contact_status": "completed",
                "owner_contact_updated_at": datetime.now(timezone.utc).isoformat(),
                "cbc_source_image_name": image_path.name,
                "cbc_extracted_address": extracted["property_address"],
            }
            bill_update = {k: v for k, v in bill_update.items() if v is not None}

            audit_row = {
                "source_image_name": image_path.name,
                "source_image_path": str(image_path),
                "matched_apn": matched_apn,
                "match_status": match_status,
                "match_address_source": matched_address_source,
                "property_address": extracted["property_address"],
                "occupancy_type": extracted["occupancy_type"],
                "ownership_type": extracted["ownership_type"],
                "last_sale_date": extracted["last_sale_date"],
                "primary_resident_name": extracted["primary_resident_name"],
                "primary_resident_age": extracted["primary_resident_age"],
                "primary_resident_phone_number": extracted["primary_resident_phone_number"],
                "deceased_count": extracted["deceased_count"],
                "important_notes": extracted["important_notes"],
                "raw_extraction": extracted,
                "raw_model_response": raw_response,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            if dry_run:
                print(f"  DRY RUN: Would update APN {matched_apn} from {image_path.name}")
                continue

            supabase.table("bills").update(bill_update).eq("apn", matched_apn).execute()
            updated += 1

            if audit_table:
                supabase.table(audit_table).insert(audit_row).execute()

            image_path.unlink()
            deleted += 1
            print(f"  Updated APN {matched_apn} and deleted {image_path.name}")
        except Exception as exc:
            failed += 1
            print(f"  Failed {image_path.name}: {exc}")

    print("\nDone.")
    print(f"Updated bills: {updated}")
    print(f"Unmatched: {unmatched}")
    print(f"Deleted: {deleted}")
    print(f"Failed: {failed}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured data from CBC images with Gemini and insert into Supabase."
    )
    parser.add_argument(
        "--image-dir",
        default=r"C:\Users\zer0p\Downloads\CBC",
        help="Directory containing images to process.",
    )
    parser.add_argument(
        "--audit-table",
        default=None,
        help="Optional table name for writing per-image extraction audit rows.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model name.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse images but skip DB inserts and file deletion.",
    )
    return parser.parse_args()


def main() -> None:
    load_env()
    args = parse_args()
    ingest_images(
        image_dir=Path(args.image_dir),
        audit_table=args.audit_table,
        model=args.model,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
