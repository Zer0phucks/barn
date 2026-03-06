#!/usr/bin/env python3
"""
Supabase-only database layer for BARN-scan.
Replaces all SQLite usage with Supabase client.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

try:
    from supabase import create_client, Client
    _client: Client | None = None
except ImportError:
    create_client = None
    Client = None
    _client = None

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY", "")
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


SUPABASE_RETRY_ATTEMPTS = max(1, _env_int("SUPABASE_RETRY_ATTEMPTS", 3))
SUPABASE_RETRY_BASE_DELAY_SECONDS = max(0.0, _env_float("SUPABASE_RETRY_BASE_DELAY_SECONDS", 0.35))

_TRANSIENT_ERROR_NAMES = {
    "RemoteProtocolError",
    "ConnectionError",
    "ConnectError",
    "ConnectTimeout",
    "ReadTimeout",
    "ReadError",
    "WriteError",
    "PoolTimeout",
    "ProtocolError",
    "TransportError",
    "TimeoutException",
    "ServerDisconnectedError",
}
_TRANSIENT_ERROR_MARKERS = (
    "connectionterminated",
    "remote protocol",
    "server disconnected",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "timed out",
    "eof occurred",
    "stream closed",
    "broken pipe",
)


def _iter_exception_chain(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        yield current
        seen.add(id(current))
        next_exc = current.__cause__ or current.__context__
        current = next_exc if isinstance(next_exc, BaseException) else None


def _is_transient_network_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if current.__class__.__name__ in _TRANSIENT_ERROR_NAMES:
            return True
        msg = str(current).lower()
        if any(marker in msg for marker in _TRANSIENT_ERROR_MARKERS):
            return True
    return False


def _patch_postgrest_execute_with_retry() -> None:
    """Monkey-patch sync PostgREST execute() with small retry for transient transport failures."""
    try:
        from postgrest._sync import request_builder as sync_rb
    except Exception:
        return

    builder_names = (
        "SyncQueryRequestBuilder",
        "SyncSingleRequestBuilder",
        "SyncExplainRequestBuilder",
        "SyncMaybeSingleRequestBuilder",
        "SyncFilterRequestBuilder",
        "SyncRPCFilterRequestBuilder",
        "SyncSelectRequestBuilder",
    )

    def _build_wrapper(original_execute):
        def _execute_with_retry(self, *args, **kwargs):
            attempt = 0
            while True:
                attempt += 1
                try:
                    return original_execute(self, *args, **kwargs)
                except Exception as exc:
                    if (
                        attempt >= SUPABASE_RETRY_ATTEMPTS
                        or not _is_transient_network_error(exc)
                    ):
                        raise
                    sleep_seconds = SUPABASE_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)

        setattr(_execute_with_retry, "_barn_retry_wrapped", True)
        return _execute_with_retry

    for name in builder_names:
        cls = getattr(sync_rb, name, None)
        if cls is None:
            continue
        execute = getattr(cls, "execute", None)
        if not callable(execute) or getattr(execute, "_barn_retry_wrapped", False):
            continue
        setattr(cls, "execute", _build_wrapper(execute))


_patch_postgrest_execute_with_retry()


def get_client() -> Client:
    """Get or create Supabase client. Raises if not configured."""
    global _client
    if not create_client:
        raise RuntimeError("supabase package not installed. Run: pip install supabase")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) must be set in .env")
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY.strip())
    return _client


# ---------------------------------------------------------------------------
# Parcels (Supabase parcels table has "APN" and row_json)
# ---------------------------------------------------------------------------

def upsert_parcel(apn: str, row_json: str | dict | None) -> None:
    row = row_json
    if isinstance(row, str):
        try:
            row = json.loads(row) if row else None
        except json.JSONDecodeError:
            row = None
    get_client().table("parcels").upsert({"APN": apn, "row_json": row}).execute()


# ---------------------------------------------------------------------------
# Bills (primary key apn)
# ---------------------------------------------------------------------------

def upsert_bill(
    apn: str,
    pdf_file: str | None = None,
    parcel_number: str | None = None,
    tracer_number: str | None = None,
    location_of_property: str | None = None,
    tax_year: str | None = None,
    last_payment: str | None = None,
    delinquent: int = 0,
    raw_text: str | None = None,
    bill_url: str | None = None,
    power_status: str | None = None,
    has_vpt: int = 0,
    vpt_marker: str | None = None,
    city: str | None = None,
    condition_score: float | None = None,
    condition_notes: str | None = None,
    condition_updated_at: str | None = None,
    streetview_image_path: str | None = None,
    research_status: str | None = None,
    research_report_path: str | None = None,
    research_updated_at: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "apn": apn,
        "pdf_file": pdf_file or "",
        "parcel_number": parcel_number,
        "tracer_number": tracer_number,
        "location_of_property": location_of_property,
        "tax_year": tax_year,
        "last_payment": last_payment,
        "delinquent": delinquent or 0,
        "raw_text": raw_text,
        "bill_url": bill_url,
        "power_status": power_status,
        "has_vpt": has_vpt or 0,
        "vpt_marker": vpt_marker,
        "city": city,
        "condition_score": condition_score,
        "condition_notes": condition_notes,
        "condition_updated_at": condition_updated_at,
        "streetview_image_path": streetview_image_path,
        "research_status": research_status,
        "research_report_path": research_report_path,
        "research_updated_at": research_updated_at,
    }
    payload = {k: v for k, v in payload.items() if v is not None or k == "apn"}
    if "pdf_file" not in payload or payload.get("pdf_file") is None:
        payload["pdf_file"] = ""
    get_client().table("bills").upsert(payload).execute()


def update_bill_power_status(apn: str, power_status: str) -> None:
    get_client().table("bills").update({"power_status": power_status}).eq("apn", apn).execute()


def update_bill_research(apn: str, research_status: str, research_report_path: str | None = None, research_updated_at: str | None = None) -> None:
    data: dict[str, Any] = {"research_status": research_status}
    if research_report_path is not None:
        data["research_report_path"] = research_report_path
    if research_updated_at is not None:
        data["research_updated_at"] = research_updated_at
    get_client().table("bills").update(data).eq("apn", apn).execute()


def update_bill_condition(apn: str, condition_score: float, condition_notes: str, condition_updated_at: str | None = None, streetview_image_path: str | None = None) -> None:
    data: dict[str, Any] = {"condition_score": condition_score, "condition_notes": condition_notes}
    if condition_updated_at is not None:
        data["condition_updated_at"] = condition_updated_at
    if streetview_image_path is not None:
        data["streetview_image_path"] = streetview_image_path
    get_client().table("bills").update(data).eq("apn", apn).execute()


def update_bill_owner_contact(
    apn: str,
    owner_contact_status: str,
    owner_email: str | None = None,
    owner_phone: str | None = None,
    owner_contact_updated_at: str | None = None,
    tenant_verified: bool | None = None,
    prop_ownership_type: str | None = None,
    prop_last_sale_date: str | None = None,
    prop_occupancy_type: str | None = None,
    owner_mobile_phone: str | None = None,
    owner_details_url: str | None = None,
    property_search_url: str | None = None,
    mailing_search_url: str | None = None,
) -> None:
    data: dict[str, Any] = {"owner_contact_status": owner_contact_status}
    if owner_email is not None:
        data["owner_email"] = owner_email
    if owner_phone is not None:
        data["owner_phone"] = owner_phone
    if owner_contact_updated_at is not None:
        data["owner_contact_updated_at"] = owner_contact_updated_at
    if tenant_verified is not None:
        data["tenant_verified"] = tenant_verified
    if prop_ownership_type is not None:
        data["prop_ownership_type"] = prop_ownership_type
    if prop_last_sale_date is not None:
        data["prop_last_sale_date"] = prop_last_sale_date
    if prop_occupancy_type is not None:
        data["prop_occupancy_type"] = prop_occupancy_type
    if owner_mobile_phone is not None:
        data["owner_mobile_phone"] = owner_mobile_phone
    if owner_details_url is not None:
        data["owner_details_url"] = owner_details_url
    if property_search_url is not None:
        data["property_search_url"] = property_search_url
    if mailing_search_url is not None:
        data["mailing_search_url"] = mailing_search_url
    get_client().table("bills").update(data).eq("apn", apn).execute()


def get_bills_missing_owner_contact() -> list[str]:
    """Return APNs where owner_contact_status is null (not yet scanned)."""
    r = get_client().table("bills").select("apn").is_("owner_contact_status", "null").execute()
    return [row["apn"] for row in (r.data or []) if row.get("apn")]


def get_bill(apn: str) -> dict[str, Any] | None:
    r = get_client().table("bills").select("*").eq("apn", apn).limit(1).execute()
    if r.data and len(r.data) > 0:
        return r.data[0]
    return None


def _normalize_research_filter(research_filter: str) -> str:
    value = (research_filter or "").strip().lower()
    aliases = {
        "all": "",
        "researched": "completed",
        "not_researched": "unchecked",
        "not-researched": "unchecked",
        "unresearched": "unchecked",
        "notresearched": "unchecked",
        "none": "unchecked",
    }
    value = aliases.get(value, value)
    allowed = {"", "completed", "unchecked", "in_progress", "failed", "pending"}
    return value if value in allowed else ""


def _is_get_bills_filtered_ambiguous_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "get_bills_filtered" in msg
        and ("pgrst203" in msg or "could not choose the best candidate function" in msg)
    )


def _get_apns_for_research_filter(research_filter: str) -> set[str]:
    normalized = _normalize_research_filter(research_filter)
    if not normalized:
        return set()

    apns: set[str] = set()
    batch_size = 1000
    offset = 0

    while True:
        query = get_client().table("bills").select("apn").range(offset, offset + batch_size - 1)
        if normalized == "unchecked":
            query = query.or_("research_status.is.null,research_status.eq.unchecked")
        else:
            query = query.eq("research_status", normalized)
        r = query.execute()
        rows = r.data or []
        if not rows:
            break
        apns.update(row["apn"] for row in rows if row.get("apn"))
        if len(rows) < batch_size:
            break
        offset += batch_size

    return apns


def _parse_get_bills_filtered_response(data: Any) -> tuple[list[dict], int]:
    if not data:
        return [], 0
    row = data[0] if isinstance(data, list) and len(data) > 0 else data
    if not isinstance(row, dict):
        return [], 0
    if "get_bills_filtered" in row:
        row = row["get_bills_filtered"]
    if not isinstance(row, dict):
        return [], 0
    total = int(row.get("total", 0))
    rows = row.get("rows") or []
    return (rows if isinstance(rows, list) else []), total


_CONTACT_FILTER_COLUMNS = (
    "prop_occupancy_type",
    "prop_ownership_type",
    "primary_resident_age",
    "deceased_count",
)

_CONTACT_ENRICH_COLUMNS = (
    "owner_name",
    "important_notes",
)

_RPC_SORT_COLUMNS = {
    "location_of_property",
    "apn",
    "parcel_number",
    "tracer_number",
    "tax_year",
    "pdf_file",
    "situs_zip",
    "last_payment",
    "delinquent",
    "power_status",
    "city",
    "has_vpt",
    "condition_score",
}


def _first_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _matches_text_filter(value: Any, filter_value: str) -> bool:
    needle = (filter_value or "").strip().lower()
    if not needle:
        return True
    return needle in str(value or "").lower()


def _matches_numeric_filter(value: Any, filter_value: str) -> bool:
    raw = (filter_value or "").strip().lower()
    if not raw:
        return True

    n = _first_int(value)
    if raw in {"null", "none", "na", "n/a", "unknown"}:
        return n is None

    plus = re.fullmatch(r"(\d+)\+", raw)
    if plus:
        return n is not None and n >= int(plus.group(1))

    rng = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw)
    if rng:
        lo = int(rng.group(1))
        hi = int(rng.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return n is not None and lo <= n <= hi

    if raw.isdigit():
        return n is not None and n == int(raw)

    return raw in str(value or "").lower()


def _row_matches_contact_filters(
    row: dict[str, Any],
    occupancy_filter: str = "",
    ownership_filter: str = "",
    primary_resident_age_filter: str = "",
    deceased_count_filter: str = "",
) -> bool:
    if not _matches_text_filter(row.get("prop_occupancy_type"), occupancy_filter):
        return False
    if not _matches_text_filter(row.get("prop_ownership_type"), ownership_filter):
        return False
    if not _matches_numeric_filter(row.get("primary_resident_age"), primary_resident_age_filter):
        return False
    if not _matches_numeric_filter(row.get("deceased_count"), deceased_count_filter):
        return False
    return True


def _fetch_bill_contact_fields_for_apns(apns: list[str]) -> dict[str, dict[str, Any]]:
    if not apns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    chunk_size = 500
    cols = ",".join(["apn", *_CONTACT_ENRICH_COLUMNS])
    for i in range(0, len(apns), chunk_size):
        chunk = apns[i : i + chunk_size]
        r = get_client().table("bills").select(cols).in_("apn", chunk).execute()
        for row in (r.data or []):
            apn = row.get("apn")
            if apn:
                out[str(apn)] = row
    return out


def _enrich_rows_with_contact_fields(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    needs_enrichment = False
    for row in rows:
        if any((col not in row) for col in _CONTACT_ENRICH_COLUMNS):
            needs_enrichment = True
            break
    if not needs_enrichment:
        return rows

    apns = [str(r.get("apn")) for r in rows if r.get("apn")]
    contact_map = _fetch_bill_contact_fields_for_apns(apns)
    for row in rows:
        apn = str(row.get("apn") or "")
        extras = contact_map.get(apn, {})
        if not extras:
            continue
        for col in _CONTACT_ENRICH_COLUMNS:
            if col not in row or row.get(col) is None:
                row[col] = extras.get(col)
    return rows


def _fetch_all_rows_for_filtered_payload(payload: dict[str, Any], normalized_research: str) -> list[dict]:
    scan_payload = dict(payload)
    scan_payload["p_limit"] = 200
    scan_payload["p_offset"] = 0
    rows_out: list[dict] = []
    scanned = 0
    allowed_apns: set[str] | None = None
    use_research_param = bool(normalized_research)

    while True:
        query_payload = dict(scan_payload)
        if use_research_param:
            query_payload["p_research"] = normalized_research
        try:
            scan_r = get_client().rpc("get_bills_filtered", query_payload).execute()
        except Exception as exc:
            if not use_research_param and _is_get_bills_filtered_ambiguous_error(exc):
                use_research_param = True
                continue
            if use_research_param:
                use_research_param = False
                allowed_apns = _get_apns_for_research_filter(normalized_research)
                if not allowed_apns:
                    return []
                continue
            raise

        rows_chunk, total_chunk = _parse_get_bills_filtered_response(scan_r.data)
        if not rows_chunk:
            break
        if allowed_apns is not None:
            rows_chunk = [row for row in rows_chunk if row.get("apn") in allowed_apns]
        rows_out.extend(rows_chunk)
        scanned += len(rows_chunk)
        scan_payload["p_offset"] += 200
        if scan_payload["p_offset"] >= total_chunk:
            break

    return rows_out


def _sort_rows_by_contact_field(rows: list[dict], sort: str, order: str) -> list[dict]:
    reverse = (order or "").lower() == "desc"
    key_col = "primary_resident_age" if sort == "primary_resident_age" else "deceased_count"
    present: list[tuple[int, dict]] = []
    missing: list[dict] = []
    for row in rows:
        n = _first_int(row.get(key_col))
        if n is None:
            missing.append(row)
        else:
            present.append((n, row))
    present.sort(key=lambda item: item[0], reverse=reverse)
    return [row for _, row in present] + missing


def get_bills_with_parcels_filtered(
    q: str = "",
    zip_filter: str = "",
    power_filter: str = "",
    fav_filter: str = "",
    city_filter: str = "",
    vpt_filter: str = "",
    delinquent_filter: str = "",
    condition_filter: str = "",
    outofstate_filter: str = "",
    research_filter: str = "",
    owner_name_filter: str = "",
    sort: str = "location_of_property",
    order: str = "asc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    """Returns (rows, total). Uses Supabase RPC get_bills_filtered."""
    if page_size == 0:
        limit = 1000000
        offset = 0
    else:
        limit = min(max(int(page_size), 10), 200)
        offset = (max(int(page), 1) - 1) * limit
    payload = {
        "p_q": (q or "").strip() or None,
        "p_zip": (zip_filter or "").strip() or None,
        "p_power": (power_filter or "").strip() or None,
        "p_fav": 1 if (fav_filter or "").strip() == "1" else None,
        "p_city": (city_filter or "").strip().upper() or None,
        "p_vpt": 1 if (vpt_filter or "").strip() == "1" else None,
        "p_delinquent": 1 if (delinquent_filter or "").strip() == "1" else None,
        "p_condition": (condition_filter or "").strip() or None,
        "p_outofstate": 1 if (outofstate_filter or "").strip() == "1" else None,
        "p_sort": ((sort or "location_of_property").strip() if (sort or "location_of_property").strip() in _RPC_SORT_COLUMNS else "location_of_property"),
        "p_order": (order or "asc").strip(),
        "p_limit": limit,
        "p_offset": offset,
        "p_research": _normalize_research_filter(research_filter) or None,
        "p_owner_name": (owner_name_filter or "").strip() or None,
    }

    r = get_client().rpc("get_bills_filtered", payload).execute()

    rows, total = _parse_get_bills_filtered_response(r.data)
    rows = _enrich_rows_with_contact_fields(rows)
    return rows, total


def get_bills_for_map(
    q: str = "",
    zip_filter: str = "",
    power_filter: str = "",
    fav_filter: str = "",
    city_filter: str = "",
    vpt_filter: str = "",
    delinquent_filter: str = "",
    owner_name_filter: str = "",
) -> list[dict]:
    payload = {
        "p_q": (q or "").strip() or None,
        "p_zip": (zip_filter or "").strip() or None,
        "p_power": (power_filter or "").strip() or None,
        "p_fav": 1 if (fav_filter or "").strip() == "1" else None,
        "p_city": (city_filter or "").strip().upper() or None,
        "p_vpt": 1 if (vpt_filter or "").strip() == "1" else None,
        "p_delinquent": 1 if (delinquent_filter or "").strip() == "1" else None,
        "p_owner_name": (owner_name_filter or "").strip() or None,
    }
    r = get_client().rpc("get_bills_for_map", payload).execute()
    if not r.data:
        return []
    data = r.data
    # RPC can return: [{"get_bills_for_map": [...]}], {"get_bills_for_map": [...]}, or [...] (array of bills)
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict) and "get_bills_for_map" in first:
            out = first["get_bills_for_map"]
            rows = out if isinstance(out, list) else []
        elif isinstance(first, dict) and "apn" in first:
            rows = data
        else:
            rows = []
        # First item is a bill row (has "apn") - data is already the list of bills
    elif isinstance(data, dict) and "get_bills_for_map" in data:
        out = data["get_bills_for_map"]
        rows = out if isinstance(out, list) else []
    else:
        rows = data if isinstance(data, list) else []

    rows = _enrich_rows_with_contact_fields(rows)
    return rows


def get_bills_count_where(**kwargs: Any) -> int:
    """Run a simple count on bills with optional .eq filters. kwargs are column=value."""
    q = get_client().table("bills").select("apn", count="exact")
    for key, val in kwargs.items():
        if val is not None:
            q = q.eq(key, val)
    r = q.limit(1).execute()
    return r.count or 0



def get_bills_missing_location() -> list[tuple[str, str]]:
    r = get_client().table("bills").select("apn, bill_url, location_of_property").execute()
    return [(row["apn"], row.get("bill_url") or "") for row in (r.data or []) if not (row.get("location_of_property") or "").strip()]


def get_bills_missing_research() -> list[str]:
    """
    Get APNs of bills that have not been researched.

    Definition of "missing research":
      - research_status is NULL, or
      - research_status == 'unchecked'
    """
    r = (
        get_client()
        .table("bills")
        .select("apn")
        .or_("research_status.is.null,research_status.eq.unchecked")
        .execute()
    )
    return [row["apn"] for row in (r.data or []) if row.get("apn")]


# ---------------------------------------------------------------------------
# Results (apn, pdf_file) - for run_all ensure_cache_in_db
# ---------------------------------------------------------------------------

def get_results_apns() -> set[str]:
    r = get_client().table("results").select("apn").execute()
    return {row["apn"] for row in (r.data or []) if row.get("apn")}


def upsert_result(apn: str, pdf_file: str | None = None) -> None:
    get_client().table("results").upsert({"apn": apn, "pdf_file": pdf_file or ""}).execute()


# ---------------------------------------------------------------------------
# Favorites (Supabase: apn, added_at)
# ---------------------------------------------------------------------------

def get_favorites_apns() -> list[str]:
    r = get_client().table("favorites").select("apn").execute()
    return [row["apn"] for row in (r.data or []) if row.get("apn")]


def add_favorite(apn: str) -> None:
    get_client().table("favorites").upsert({"apn": apn}).execute()


def remove_favorite(apn: str) -> None:
    get_client().table("favorites").delete().eq("apn", apn).execute()


def has_favorite(apn: str) -> bool:
    r = get_client().table("favorites").select("apn").eq("apn", apn).limit(1).execute()
    return bool(r.data and len(r.data) > 0)


def toggle_favorite(apn: str) -> bool:
    if has_favorite(apn):
        remove_favorite(apn)
        return False
    add_favorite(apn)
    return True


# ---------------------------------------------------------------------------
# Bills + Parcels joined (for property info, coords, etc.)
# ---------------------------------------------------------------------------

def get_bill_with_parcel(apn: str) -> dict[str, Any] | None:
    """Return one bill row with parcel row_json joined (for get_property_info)."""
    bill = get_bill(apn)
    if not bill:
        return None
    # Parcels table uses "APN" - fetch parcel
    r = get_client().table("parcels").select("row_json").eq("APN", apn).limit(1).execute()
    row_json = None
    if r.data and len(r.data) > 0:
        row_json = r.data[0].get("row_json")
    bill["row_json"] = row_json
    return bill


# ---------------------------------------------------------------------------
# Lists (lists + list_properties)
# ---------------------------------------------------------------------------

def ensure_lists_tables() -> None:
    """No-op for Supabase; tables already exist."""
    pass


def get_lists() -> list[dict]:
    r = get_client().table("lists").select("id, name, description, created_at").order("name").execute()
    lists = []
    for row in r.data or []:
        cp = get_client().table("list_properties").select("id", count="exact").eq("list_id", row["id"]).execute()
        lists.append({
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description"),
            "created_at": row.get("created_at"),
            "property_count": cp.count or 0,
        })
    return lists


def create_list(name: str, description: str | None = None) -> int:
    r = get_client().table("lists").insert({"name": name, "description": description or ""}).execute()
    if r.data and len(r.data) > 0:
        return int(r.data[0]["id"])
    raise RuntimeError("Failed to create list")


def get_list(list_id: int) -> dict | None:
    r = get_client().table("lists").select("*").eq("id", list_id).limit(1).execute()
    if r.data and len(r.data) > 0:
        return r.data[0]
    return None


def delete_list(list_id: int) -> bool:
    get_client().table("list_properties").delete().eq("list_id", list_id).execute()
    r = get_client().table("lists").delete().eq("id", list_id).execute()
    return bool(r.data)


def get_list_properties(list_id: int) -> list[dict]:
    # Join list_properties -> bills -> parcels for full rows
    lp = get_client().table("list_properties").select("apn, sort_order").eq("list_id", list_id).order("sort_order").execute()
    if not lp.data:
        return []
    apns = [row["apn"] for row in lp.data]
    if not apns:
        return []
    bills = get_client().table("bills").select("apn, location_of_property, city, has_vpt, condition_score").in_("apn", apns).execute()
    bill_map = {b["apn"]: b for b in (bills.data or [])}
    out = []
    for row in lp.data:
        apn = row["apn"]
        b = bill_map.get(apn, {})
        parcel_r = get_client().table("parcels").select("row_json").eq("APN", apn).limit(1).execute()
        row_json = parcel_r.data[0].get("row_json") if (parcel_r.data and len(parcel_r.data) > 0) else None
        out.append({
            "apn": apn,
            "location_of_property": b.get("location_of_property"),
            "city": b.get("city"),
            "has_vpt": b.get("has_vpt"),
            "condition_score": b.get("condition_score"),
            "row_json": row_json,
            "sort_order": row.get("sort_order"),
        })
    return out


def add_properties_to_list(list_id: int, apns: list[str]) -> int:
    """Add a list of APNs to a list. Returns number added (skips already present)."""
    if not apns:
        return 0
    existing = get_client().table("list_properties").select("apn").eq("list_id", list_id).execute()
    existing_apns = {row["apn"] for row in (existing.data or [])}
    max_order_r = get_client().table("list_properties").select("sort_order").eq("list_id", list_id).order("sort_order", desc=True).limit(1).execute()
    sort_order = (max_order_r.data[0]["sort_order"] + 1) if max_order_r.data else 0
    added = 0
    for i, apn in enumerate(apns):
        if apn in existing_apns:
            continue
        get_client().table("list_properties").upsert({"list_id": list_id, "apn": apn, "sort_order": sort_order + i}).execute()
        existing_apns.add(apn)
        added += 1
    return added


def add_properties_to_list_from_filter(
    list_id: int,
    q: str = "",
    zip_filter: str = "",
    power_filter: str = "",
    city_filter: str = "",
    vpt_filter: str = "",
    delinquent_filter: str = "",
    condition_filter: str = "",
    outofstate_filter: str = "",
    research_filter: str = "",
    owner_name_filter: str = "",
    occupancy_filter: str = "",
    ownership_filter: str = "",
    primary_resident_age_filter: str = "",
    deceased_count_filter: str = "",
    limit: int = 500,
) -> int:
    rows, _ = get_bills_with_parcels_filtered(
        q=q,
        zip_filter=zip_filter,
        power_filter=power_filter,
        city_filter=city_filter,
        vpt_filter=vpt_filter,
        delinquent_filter=delinquent_filter,
        condition_filter=condition_filter,
        outofstate_filter=outofstate_filter,
        research_filter=research_filter,
        owner_name_filter=owner_name_filter,
        page=1,
        page_size=limit,
    )
    apns = [r["apn"] for r in rows if r.get("apn")]
    if not apns:
        return 0
    existing = get_client().table("list_properties").select("apn").eq("list_id", list_id).execute()
    existing_apns = {row["apn"] for row in (existing.data or [])}
    max_order_r = get_client().table("list_properties").select("sort_order").eq("list_id", list_id).order("sort_order", desc=True).limit(1).execute()
    sort_order = (max_order_r.data[0]["sort_order"] + 1) if max_order_r.data else 0
    added = 0
    for i, apn in enumerate(apns):
        if apn in existing_apns:
            continue
        get_client().table("list_properties").upsert({"list_id": list_id, "apn": apn, "sort_order": sort_order + i}).execute()
        existing_apns.add(apn)
        added += 1
    return added


def remove_property_from_list(list_id: int, apn: str) -> bool:
    r = get_client().table("list_properties").delete().eq("list_id", list_id).eq("apn", apn).execute()
    return bool(r.data)


def get_list_route_waypoints(list_id: int) -> list[dict]:
    lp = get_client().table("list_properties").select("apn, sort_order").eq("list_id", list_id).order("sort_order").execute()
    if not lp.data:
        return []
    waypoints = []
    for row in lp.data:
        apn = row["apn"]
        bill = get_client().table("bills").select("apn, location_of_property").eq("apn", apn).limit(1).execute()
        parcel = get_client().table("parcels").select("row_json").eq("APN", apn).limit(1).execute()
        loc = bill.data[0].get("location_of_property") if (bill.data and len(bill.data) > 0) else ""
        row_json = parcel.data[0].get("row_json") if (parcel.data and len(parcel.data) > 0) else None
        try:
            p = json.loads(row_json) if isinstance(row_json, str) else (row_json or {})
            x = float(p.get("CENTROID_X") or p.get("X_CORD") or 0)
            y = float(p.get("CENTROID_Y") or p.get("Y_CORD") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if x and y:
            import math
            lng = (x / 20037508.34) * 180
            lat = (y / 20037508.34) * 180
            lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
            waypoints.append({"lat": lat, "lng": lng, "address": loc})
    return waypoints


# ---------------------------------------------------------------------------
# Scouting (scouting_collections, collection_properties, scout_results)
# ---------------------------------------------------------------------------

def ensure_scout_tables() -> None:
    pass


def get_scout_collections() -> list[dict]:
    r = get_client().table("scouting_collections").select("id, name, description, created_at").order("name").execute()
    out = []
    for row in r.data or []:
        cp = get_client().table("collection_properties").select("id", count="exact").eq("collection_id", row["id"]).execute()
        sr = get_client().table("scout_results").select("apn", count="exact").eq("collection_id", row["id"]).execute()
        out.append({
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description"),
            "created_at": row.get("created_at"),
            "property_count": cp.count or 0,
            "scouted_count": sr.count or 0,
        })
    return out


def create_scout_collection(name: str, description: str | None = None, apns: list[str] | None = None) -> int:
    r = get_client().table("scouting_collections").insert({"name": name, "description": description or ""}).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to create collection")
    cid = int(r.data[0]["id"])
    if apns:
        for i, apn in enumerate(apns):
            get_client().table("collection_properties").upsert({"collection_id": cid, "apn": apn, "sort_order": i}).execute()
    return cid


def delete_scout_collection(collection_id: int) -> bool:
    get_client().table("scout_results").delete().eq("collection_id", collection_id).execute()
    get_client().table("collection_properties").delete().eq("collection_id", collection_id).execute()
    r = get_client().table("scouting_collections").delete().eq("id", collection_id).execute()
    return bool(r.data)


def get_collection_properties(collection_id: int) -> list[dict]:
    cp = get_client().table("collection_properties").select("apn, sort_order").eq("collection_id", collection_id).order("sort_order").execute()
    if not cp.data:
        return []
    apns = [row["apn"] for row in cp.data]
    bills = get_client().table("bills").select("apn, location_of_property, has_vpt, condition_score, city, streetview_image_path").in_("apn", apns).execute()
    bill_map = {b["apn"]: b for b in (bills.data or [])}
    out = []
    for row in cp.data:
        apn = row["apn"]
        b = bill_map.get(apn, {})
        parcel_r = get_client().table("parcels").select("row_json").eq("APN", apn).limit(1).execute()
        row_json = parcel_r.data[0].get("row_json") if (parcel_r.data and len(parcel_r.data) > 0) else None
        out.append({"apn": apn, "sort_order": row.get("sort_order"), "row_json": row_json, **b})
    return out


def add_properties_to_collection(collection_id: int, apns: list[str]) -> int:
    existing = get_client().table("collection_properties").select("apn").eq("collection_id", collection_id).execute()
    existing_apns = {row["apn"] for row in (existing.data or [])}
    max_r = get_client().table("collection_properties").select("sort_order").eq("collection_id", collection_id).order("sort_order", desc=True).limit(1).execute()
    sort_order = (max_r.data[0]["sort_order"] + 1) if max_r.data else 0
    added = 0
    for i, apn in enumerate(apns):
        if apn in existing_apns:
            continue
        get_client().table("collection_properties").upsert({"collection_id": collection_id, "apn": apn, "sort_order": sort_order + i}).execute()
        added += 1
    return added


def remove_property_from_collection(collection_id: int, apn: str) -> bool:
    r = get_client().table("collection_properties").delete().eq("collection_id", collection_id).eq("apn", apn).execute()
    return bool(r.data)


def get_scout_results(collection_id: int | None = None) -> list[dict]:
    q = get_client().table("scout_results").select("id, apn, collection_id, follow_up, flyered, notes, scouted_at, latitude, longitude")
    if collection_id is not None:
        q = q.eq("collection_id", collection_id)
    r = q.order("scouted_at", desc=True).execute()
    return r.data or []


def upsert_scout_result(apn: str, collection_id: int | None = None, follow_up: int = 0, flyered: int = 0, notes: str | None = None, latitude: float | None = None, longitude: float | None = None) -> int:
    payload = {"apn": apn, "follow_up": follow_up, "flyered": flyered, "notes": notes or "", "latitude": latitude, "longitude": longitude}
    if collection_id is not None:
        payload["collection_id"] = collection_id
    r = get_client().table("scout_results").upsert(payload).execute()
    if r.data and len(r.data) > 0:
        return int(r.data[0]["id"])
    return 0


def get_scout_stats() -> dict:
    total = get_client().table("scout_results").select("id", count="exact").execute()
    follow_ups = get_client().table("scout_results").select("id", count="exact").eq("follow_up", 1).execute()
    flyered = get_client().table("scout_results").select("id", count="exact").eq("flyered", 1).execute()
    unique = get_client().rpc("get_distinct_apn_count_scout_results", {}).execute() if False else None
    # If no RPC, count distinct by fetching (simplified)
    return {
        "total": total.count or 0,
        "follow_ups": follow_ups.count or 0,
        "flyered": flyered.count or 0,
        "unique_properties": total.count or 0,
    }


def get_bills_for_export(
    q: str = "",
    zip_filter: str = "",
    power_filter: str = "",
    city_filter: str = "",
    vpt_filter: str = "",
    delinquent_filter: str = "",
    condition_filter: str = "",
    owner_name_filter: str = "",
    list_id: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Fetch bills with optional filters for export/CSV. Uses RPC or table."""
    rows, _ = get_bills_with_parcels_filtered(q=q, zip_filter=zip_filter, power_filter=power_filter, city_filter=city_filter, vpt_filter=vpt_filter, delinquent_filter=delinquent_filter, condition_filter=condition_filter, owner_name_filter=owner_name_filter, page=offset // limit + 1, page_size=limit)
    if list_id is not None:
        lp = get_client().table("list_properties").select("apn").eq("list_id", list_id).execute()
        list_apns = {row["apn"] for row in (lp.data or [])}
        rows = [r for r in rows if r.get("apn") in list_apns]
    return rows


def get_bills_for_export_count(
    q: str = "",
    zip_filter: str = "",
    power_filter: str = "",
    city_filter: str = "",
    vpt_filter: str = "",
    delinquent_filter: str = "",
    condition_filter: str = "",
    owner_name_filter: str = "",
    list_id: int | None = None,
) -> int:
    rows, total = get_bills_with_parcels_filtered(q=q, zip_filter=zip_filter, power_filter=power_filter, city_filter=city_filter, vpt_filter=vpt_filter, delinquent_filter=delinquent_filter, condition_filter=condition_filter, owner_name_filter=owner_name_filter, page=1, page_size=10000 if list_id else 1)
    if list_id is not None:
        lp = get_client().table("list_properties").select("apn").eq("list_id", list_id).execute()
        list_apns = {row["apn"] for row in (lp.data or [])}
        return len([r for r in rows if r.get("apn") in list_apns])
    return total


# ---------------------------------------------------------------------------
# Outreach Pipeline
# ---------------------------------------------------------------------------

OUTREACH_STAGES = [
    "identified", "qualified", "outreach_ready", "contacted",
    "responding", "negotiating", "partnered", "declined", "no_response",
]


def calculate_outreach_score(bill: dict) -> float:
    """Calculate outreach readiness score (0-100) for a property."""
    score = 0.0
    has_email = bool(bill.get("owner_email"))

    # Has owner email (25 pts) -- required for email outreach
    if has_email:
        score += 25.0

    # VPT status (20 pts)
    if bill.get("has_vpt"):
        score += 20.0

    # Delinquent (15 pts)
    if bill.get("delinquent"):
        score += 15.0

    # Power off (15 pts)
    if bill.get("power_status") == "off":
        score += 15.0

    # Poor condition (10 pts)
    cond = bill.get("condition_score")
    if cond is not None and cond < 5.0:
        score += 10.0

    # Out-of-state owner (10 pts)
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        import json
        try:
            row_json = json.loads(row_json)
        except (json.JSONDecodeError, TypeError):
            row_json = {}
    mail_state = (row_json.get("MailState") or "").upper()
    if mail_state and mail_state != "CA":
        score += 10.0

    # Research completed (5 pts)
    if bill.get("research_status") == "completed":
        score += 5.0

    # Cap at 30 if no email
    if not has_email:
        score = min(score, 30.0)

    return round(score, 1)


def calculate_contact_completeness(bill: dict) -> float:
    """Calculate contact data completeness (0-100%)."""
    score = 0.0
    if bill.get("owner_email"):
        score += 40.0
    if bill.get("owner_phone") or bill.get("owner_mobile_phone"):
        score += 20.0
    # Check mailing address from parcel data
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        import json
        try:
            row_json = json.loads(row_json)
        except (json.JSONDecodeError, TypeError):
            row_json = {}
    if row_json.get("MailAddress"):
        score += 20.0
    if bill.get("primary_resident_name"):
        score += 20.0
    return round(score, 1)


def determine_outreach_stage(bill: dict, outreach: dict | None = None) -> str:
    """Determine the current outreach stage for a property."""
    if outreach:
        # If manually set to terminal stages, respect that
        if outreach.get("stage") in ("partnered", "declined", "no_response"):
            return outreach["stage"]
        if outreach.get("stage") == "negotiating":
            return "negotiating"
        if outreach.get("last_response_at"):
            return "responding"
        if outreach.get("contacted_at"):
            return "contacted"

    score = calculate_outreach_score(bill)
    has_email = bool(bill.get("owner_email"))
    has_research = bill.get("research_status") == "completed"

    if has_email and has_research and score >= 50:
        return "outreach_ready"
    if score >= 50:
        return "qualified"
    return "identified"


def upsert_outreach(apn: str, **kwargs) -> None:
    """Create or update an outreach record for a property."""
    payload = {"apn": apn, "updated_at": "now()"}
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    get_client().table("outreach").upsert(payload, on_conflict="apn").execute()


def get_outreach(apn: str) -> dict | None:
    """Get outreach record for a property."""
    resp = get_client().table("outreach").select("*").eq("apn", apn).execute()
    rows = resp.data or []
    return rows[0] if rows else None


def get_outreach_messages(apn: str, limit: int = 50) -> list[dict]:
    """Get outreach messages for a property, newest first."""
    resp = (
        get_client()
        .table("outreach_messages")
        .select("*")
        .eq("apn", apn)
        .order("sent_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def insert_outreach_message(
    apn: str,
    direction: str,
    content: str,
    channel: str = "email",
    subject: str | None = None,
    from_address: str | None = None,
    to_address: str | None = None,
    openclaw_message_id: str | None = None,
) -> None:
    """Log an outreach message."""
    payload = {
        "apn": apn,
        "direction": direction,
        "channel": channel,
        "content": content,
    }
    if subject:
        payload["subject"] = subject
    if from_address:
        payload["from_address"] = from_address
    if to_address:
        payload["to_address"] = to_address
    if openclaw_message_id:
        payload["openclaw_message_id"] = openclaw_message_id
    get_client().table("outreach_messages").insert(payload).execute()


def get_outreach_pipeline_counts() -> dict[str, int]:
    """Get count of properties at each pipeline stage."""
    counts = {}
    for stage in OUTREACH_STAGES:
        resp = (
            get_client()
            .table("outreach")
            .select("id", count="exact")
            .eq("stage", stage)
            .execute()
        )
        counts[stage] = resp.count or 0
    return counts


def get_outreach_list(
    stage: str | None = None,
    min_score: float | None = None,
    city: str | None = None,
    sort: str = "outreach_score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get filtered list of outreach records joined with bill data."""
    query = (
        get_client()
        .table("outreach")
        .select("*, bills!inner(location_of_property, city, owner_email, has_vpt, delinquent, power_status, condition_score, research_status)", count="exact")
    )
    if stage:
        query = query.eq("stage", stage)
    if min_score is not None:
        query = query.gte("outreach_score", min_score)
    if city:
        query = query.eq("bills.city", city)

    desc = order.lower() == "desc"
    query = query.order(sort, desc=desc).range(offset, offset + limit - 1)

    resp = query.execute()
    return resp.data or [], resp.count or 0


def update_outreach_stage(apn: str, stage: str, **kwargs) -> None:
    """Update the pipeline stage for a property."""
    if stage not in OUTREACH_STAGES:
        raise ValueError(f"Invalid stage: {stage}. Must be one of {OUTREACH_STAGES}")
    payload = {"stage": stage, "updated_at": "now()"}
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    get_client().table("outreach").update(payload).eq("apn", apn).execute()


def recalculate_outreach_scores(apns: list[str] | None = None) -> int:
    """Recalculate outreach scores for given APNs (or all). Returns count updated."""
    PAGE = 1000
    bills: list[dict] = []
    if apns:
        # Fetch in chunks to stay under the PostgREST row limit
        for i in range(0, len(apns), PAGE):
            chunk = apns[i : i + PAGE]
            resp = get_client().table("bills").select("*").in_("apn", chunk).execute()
            bills.extend(resp.data or [])
    else:
        # Page through all rows — PostgREST caps unranged queries at 1,000
        offset = 0
        while True:
            resp = get_client().table("bills").select("*").range(offset, offset + PAGE - 1).execute()
            page = resp.data or []
            bills.extend(page)
            if len(page) < PAGE:
                break
            offset += PAGE
    updated = 0
    for bill in bills:
        score = calculate_outreach_score(bill)
        completeness = calculate_contact_completeness(bill)
        stage = determine_outreach_stage(bill, get_outreach(bill["apn"]))

        # Update bills table
        get_client().table("bills").update({
            "outreach_score": score,
            "contact_completeness": completeness,
            "outreach_stage": stage,
        }).eq("apn", bill["apn"]).execute()

        # Upsert outreach record
        upsert_outreach(bill["apn"], outreach_score=score, stage=stage)
        updated += 1

    return updated


def get_outreach_setting(key: str, default: str = "") -> str:
    """Get an outreach setting value."""
    resp = get_client().table("outreach_settings").select("value").eq("key", key).execute()
    rows = resp.data or []
    return rows[0]["value"] if rows else default


def set_outreach_setting(key: str, value: str) -> None:
    """Set an outreach setting value."""
    get_client().table("outreach_settings").upsert(
        {"key": key, "value": value, "updated_at": "now()"},
        on_conflict="key",
    ).execute()


def delete_bill(apn: str) -> bool:
    """Delete a property from the bills table. Returns True if a row was deleted."""
    # Delete from dependent tables first to satisfy foreign key constraints
    get_client().table("outreach").delete().eq("apn", apn).execute()
    r = get_client().table("bills").delete().eq("apn", apn).execute()
    return bool(r.data)


def bulk_delete_bills(apns: list[str]) -> int:
    """Delete multiple properties. Returns count of deleted rows."""
    if not apns:
        return 0
    PAGE = 100
    deleted = 0
    for i in range(0, len(apns), PAGE):
        chunk = apns[i : i + PAGE]
        # Delete from dependent tables first to satisfy foreign key constraints
        get_client().table("outreach").delete().in_("apn", chunk).execute()
        r = get_client().table("bills").delete().in_("apn", chunk).execute()
        deleted += len(r.data or [])
    return deleted


def bulk_add_favorites(apns: list[str]) -> int:
    """Add multiple APNs to favorites. Returns count inserted."""
    if not apns:
        return 0
    PAGE = 100
    added = 0
    for i in range(0, len(apns), PAGE):
        chunk = apns[i : i + PAGE]
        rows = [{"apn": apn} for apn in chunk]
        r = get_client().table("favorites").upsert(rows).execute()
        added += len(r.data or [])
    return added


def get_distinct_zips() -> list[str]:
    """Fetch distinct zip codes from parcels."""
    r = get_client().rpc("get_distinct_zips").execute()
    data = r.data
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "distinct_zip" in data[0]:
        return [row["distinct_zip"] for row in data]
    elif isinstance(data, list) and all(isinstance(x, str) for x in data):
        return data
    return []


def update_property_notes(apn: str, important_notes: str) -> None:
    data: dict[str, Any] = {"important_notes": important_notes}
    get_client().table("bills").update(data).eq("apn", apn).execute()


def update_bill_fields(apn: str, fields: dict[str, Any]) -> None:
    """Update arbitrary allowed fields on a bills row."""
    if not fields:
        return
    get_client().table("bills").update(fields).eq("apn", apn).execute()
