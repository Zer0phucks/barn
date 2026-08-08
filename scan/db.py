#!/usr/bin/env python3
"""
Supabase-only database layer for BARN-scan.
Replaces all SQLite usage with Supabase client.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent

# webgui/db.py loads this module by file path (spec_from_file_location), which
# does not put scan/ on sys.path. Guard so the geo_utils import below resolves
# whether we're imported as `db`, exec'd from webgui/, or run from Vercel.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from geo_utils import derive_latlng  # noqa: E402

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
# Parcels (Supabase parcels table: lowercase apn PK + row_json jsonb)
# ---------------------------------------------------------------------------

def upsert_parcel(apn: str, row_json: str | dict | None) -> None:
    row = row_json
    if isinstance(row, str):
        try:
            row = json.loads(row) if row else None
        except json.JSONDecodeError:
            row = None
    get_client().table("parcels").upsert({"apn": apn, "row_json": row}).execute()


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
    lat: float | None = None,
    lng: float | None = None,
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
        # geom is derived from these by the bills_set_geom trigger; never write
        # geom directly.
        "lat": lat,
        "lng": lng,
    }
    # None-filtering is load-bearing: PostgREST's merge-duplicates upsert only
    # touches columns present in the payload, so a re-scrape must not send
    # nulls for enrichment columns (condition_score, research_status, ...) it
    # knows nothing about.
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


def _is_get_bills_filtered_missing_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "get_bills_filtered" in msg
        and (
            "could not find the function public.get_bills_filtered" in msg
            or "function public.get_bills_filtered" in msg
        )
    )


def _is_get_bills_filtered_missing_added_at_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "added_at" in msg and "does not exist" in msg


def _is_rpc_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "42501" in msg or "authenticated session" in msg


def _execute_get_bills_filtered_rpc(
    payload: dict[str, Any],
    owner_name_filter: str = "",
) -> Any:
    owner_name = (owner_name_filter or "").strip()
    attempts: list[dict[str, Any]] = []

    newest_payload = dict(payload)
    newest_payload["p_owner_name"] = owner_name
    attempts.append(newest_payload)

    current_payload = dict(payload)
    attempts.append(current_payload)

    if "p_research" in current_payload:
        legacy_payload = dict(current_payload)
        legacy_payload.pop("p_research", None)
        attempts.append(legacy_payload)

    last_exc: Exception | None = None
    for index, candidate in enumerate(attempts):
        try:
            return get_client().rpc("get_bills_filtered", candidate).execute()
        except Exception as exc:
            last_exc = exc
            is_last_attempt = index == len(attempts) - 1
            if is_last_attempt:
                raise
            if _is_get_bills_filtered_missing_error(exc) or _is_get_bills_filtered_ambiguous_error(exc):
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("get_bills_filtered RPC did not execute")


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
    "added_at",
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
            scan_r = _execute_get_bills_filtered_rpc(query_payload)
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


_DIRECT_BILL_COLUMNS = (
    "apn",
    "added_at",
    "pdf_file",
    "bill_url",
    "parcel_number",
    "tracer_number",
    "location_of_property",
    "tax_year",
    "last_payment",
    "delinquent",
    "power_status",
    "has_vpt",
    "vpt_marker",
    "city",
    "condition_score",
    "condition_notes",
    "streetview_image_path",
    "property_search_url",
    "mailing_search_url",
    "research_status",
    "situs_zip",
    "owner_name",
    "important_notes",
)


def _escape_postgrest_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace(",", "\\,")


def _parse_row_json_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _attach_parcel_row_json(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    apns = [str(row.get("apn") or "") for row in rows if row.get("apn")]
    if not apns:
        return rows

    parcel_map: dict[str, Any] = {}
    chunk_size = 100
    for index in range(0, len(apns), chunk_size):
        chunk = apns[index : index + chunk_size]
        result = get_client().table("parcels").select("apn,row_json").in_("apn", chunk).execute()
        for parcel_row in (result.data or []):
            apn = str(parcel_row.get("apn") or "")
            if apn:
                parcel_map[apn] = parcel_row.get("row_json")

    for row in rows:
        apn = str(row.get("apn") or "")
        row["row_json"] = parcel_map.get(apn)
        row.setdefault("added_at", None)

    return rows


def _row_matches_basic_fallback_filters(
    row: dict[str, Any],
    q: str = "",
    zip_filter: str = "",
    owner_name_filter: str = "",
    outofstate_filter: str = "",
) -> bool:
    query = (q or "").strip().lower()
    if query:
        haystacks = (
            str(row.get("location_of_property") or "").lower(),
            str(row.get("apn") or "").lower(),
            str(row.get("owner_name") or "").lower(),
        )
        if not any(query in haystack for haystack in haystacks):
            return False

    owner_name = (owner_name_filter or "").strip().lower()
    if owner_name and owner_name not in str(row.get("owner_name") or "").lower():
        return False

    zip_tokens = [token.strip().lower() for token in (zip_filter or "").split(",") if token.strip()]
    if zip_tokens:
        apn = str(row.get("apn") or "").lower()
        location = str(row.get("location_of_property") or "").lower()
        if not any(apn.startswith(token) or token in location for token in zip_tokens):
            return False

    if (outofstate_filter or "").strip() == "1":
        parcel = _parse_row_json_value(row.get("row_json"))
        mail_state = str(parcel.get("MailState") or "").strip().upper()
        if not mail_state or mail_state == "CA":
            return False

    return True


def _fallback_sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, (int, float)):
        return (0, value)
    return (0, str(value).lower())


def _sort_fallback_rows(rows: list[dict[str, Any]], sort: str, order: str) -> list[dict[str, Any]]:
    sort_col = (sort or "location_of_property").strip()
    if sort_col == "added_at":
        sort_col = "location_of_property"
    reverse = (order or "").lower() == "desc"
    return sorted(rows, key=lambda row: _fallback_sort_key(row.get(sort_col)), reverse=reverse)


def _fetch_bills_direct_fallback(
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
    client = get_client()
    rows: list[dict[str, Any]] = []
    batch_size = 500
    offset = 0
    favorites_apns = get_favorites_apns() if (fav_filter or "").strip() == "1" else []
    if (fav_filter or "").strip() == "1" and not favorites_apns:
        return [], 0

    normalized_research = _normalize_research_filter(research_filter)
    direct_columns = ",".join(_DIRECT_BILL_COLUMNS)

    while True:
        query = client.table("bills").select(direct_columns).range(offset, offset + batch_size - 1)
        if (power_filter or "").strip():
            query = query.eq("power_status", (power_filter or "").strip())
        if (city_filter or "").strip():
            query = query.eq("city", (city_filter or "").strip().upper())
        if (vpt_filter or "").strip() == "1":
            query = query.eq("has_vpt", 1)
        if (delinquent_filter or "").strip() == "1":
            query = query.eq("delinquent", 1)
        if favorites_apns:
            query = query.in_("apn", favorites_apns)

        condition_value = (condition_filter or "").strip().lower()
        if condition_value == "good":
            query = query.gte("condition_score", 7)
        elif condition_value == "fair":
            query = query.gte("condition_score", 4).lt("condition_score", 7)
        elif condition_value == "poor":
            query = query.lt("condition_score", 4)
        elif condition_value == "unscored":
            query = query.is_("condition_score", "null")

        if normalized_research == "unchecked":
            query = query.or_("research_status.is.null,research_status.eq.unchecked")
        elif normalized_research:
            query = query.eq("research_status", normalized_research)

        result = query.execute()
        chunk = list(result.data or [])
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < batch_size:
            break
        offset += batch_size

    # Only fetch heavy row_json upfront when outofstate filter needs it
    need_row_json_early = (outofstate_filter or "").strip() == "1"
    if need_row_json_early:
        rows = _attach_parcel_row_json(rows)

    rows = [
        row
        for row in rows
        if _row_matches_basic_fallback_filters(
            row,
            q=q,
            zip_filter=zip_filter,
            owner_name_filter=owner_name_filter,
            outofstate_filter=outofstate_filter,
        )
    ]
    rows = _sort_fallback_rows(rows, sort=sort, order=order)
    total = len(rows)

    if page_size == 0:
        if not need_row_json_early:
            rows = _attach_parcel_row_json(rows)
        return rows, total

    limit = min(max(int(page_size), 10), 200)
    page_number = max(int(page), 1)
    start = (page_number - 1) * limit
    end = start + limit
    paged_rows = rows[start:end]

    if not need_row_json_early:
        paged_rows = _attach_parcel_row_json(paged_rows)

    paged_rows = _enrich_rows_with_contact_fields(paged_rows)
    return paged_rows, total


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
    }
    try:
        r = _execute_get_bills_filtered_rpc(payload, owner_name_filter=owner_name_filter)
    except Exception as exc:
        if _is_get_bills_filtered_missing_added_at_error(exc) or _is_rpc_auth_error(exc):
            return _fetch_bills_direct_fallback(
                q=q,
                zip_filter=zip_filter,
                power_filter=power_filter,
                fav_filter=fav_filter,
                city_filter=city_filter,
                vpt_filter=vpt_filter,
                delinquent_filter=delinquent_filter,
                condition_filter=condition_filter,
                outofstate_filter=outofstate_filter,
                research_filter=research_filter,
                owner_name_filter=owner_name_filter,
                sort=sort,
                order=order,
                page=page,
                page_size=page_size,
            )
        raise

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


def count_bills_missing_research() -> int:
    """Count bills where research_status is NULL or 'unchecked'."""
    r = (
        get_client()
        .table("bills")
        .select("apn", count="exact")
        .or_("research_status.is.null,research_status.eq.unchecked")
        .limit(1)
        .execute()
    )
    return r.count or 0


def get_bills_missing_research(limit: int | None = None, offset: int = 0) -> list[str]:
    """
    Get APNs of bills that have not been researched.

    Definition of "missing research":
      - research_status is NULL, or
      - research_status == 'unchecked'

    When limit is set, returns a stable page via order(apn) and range (for batch APIs).
    When limit is None, returns all matching APNs (legacy behavior).
    """
    q = (
        get_client()
        .table("bills")
        .select("apn")
        .or_("research_status.is.null,research_status.eq.unchecked")
        .order("apn")
    )
    if limit is not None:
        if limit <= 0:
            return []
        q = q.range(offset, offset + limit - 1)
    r = q.execute()
    return [row["apn"] for row in (r.data or []) if row.get("apn")]


def update_bill_ai_vacancy(
    apn: str,
    *,
    verdict: str | None = None,
    confidence: float | None = None,
    rationale: str | None = None,
) -> None:
    """Persist structured AI vacancy fields from deep research (additive; does not change has_vpt)."""
    from datetime import datetime as _dt

    now = _dt.now().isoformat()
    data: dict[str, Any] = {"ai_vacancy_updated_at": now}
    if verdict is not None:
        data["ai_vacancy_verdict"] = verdict
    if confidence is not None:
        data["ai_vacancy_confidence"] = confidence
    if rationale is not None:
        data["ai_vacancy_rationale"] = rationale
    get_client().table("bills").update(data).eq("apn", apn).execute()


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

# ---------------------------------------------------------------------------
# Favorites.
#
# The standalone `favorites` table is gone: it duplicated list_properties for
# a single implicit list. Favorites are now rows in the list named 'Favorites'
# (seeded by supabase/migrations/20260807000003_scouting.sql), so one mechanism
# backs both. The public function names are unchanged — routes, templates and
# callers keep working.
# ---------------------------------------------------------------------------

FAVORITES_LIST_NAME = "Favorites"
_favorites_list_id: int | None = None


def get_favorites_list_id(create: bool = False) -> int | None:
    """Resolve (and cache) the id of the Favorites list.

    The list is seeded by migration, so a miss means something is off. Reads
    pass create=False and tolerate None rather than 500 the whole map page over
    a favorites overlay; writes pass create=True because they need a real id.
    """
    global _favorites_list_id
    if _favorites_list_id is not None:
        return _favorites_list_id
    r = (
        get_client()
        .table("lists")
        .select("id")
        .eq("name", FAVORITES_LIST_NAME)
        .limit(1)
        .execute()
    )
    if r.data:
        _favorites_list_id = int(r.data[0]["id"])
    elif create:
        _favorites_list_id = create_list(FAVORITES_LIST_NAME, "Ad-hoc saved properties")
    return _favorites_list_id


def get_favorites_apns() -> list[str]:
    list_id = get_favorites_list_id()
    if list_id is None:
        return []
    r = (
        get_client()
        .table("list_properties")
        .select("apn")
        .eq("list_id", list_id)
        .execute()
    )
    return [row["apn"] for row in (r.data or []) if row.get("apn")]


def add_favorite(apn: str) -> None:
    add_properties_to_list(get_favorites_list_id(create=True), [apn])


def remove_favorite(apn: str) -> None:
    list_id = get_favorites_list_id()
    if list_id is not None:
        remove_property_from_list(list_id, apn)


def has_favorite(apn: str) -> bool:
    list_id = get_favorites_list_id()
    if list_id is None:
        return False
    r = (
        get_client()
        .table("list_properties")
        .select("apn")
        .eq("list_id", list_id)
        .eq("apn", apn)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def toggle_favorite(apn: str) -> bool:
    if has_favorite(apn):
        remove_favorite(apn)
        return False
    add_favorite(apn)
    return True


def bulk_add_favorites(apns: list[str]) -> int:
    """Add multiple APNs to favorites. Returns count inserted."""
    if not apns:
        return 0
    return add_properties_to_list(get_favorites_list_id(create=True), apns)


# ---------------------------------------------------------------------------
# Bills + Parcels joined (for property info, coords, etc.)
# ---------------------------------------------------------------------------

def get_bill_with_parcel(apn: str) -> dict[str, Any] | None:
    """Return one bill row with parcel row_json joined (for get_property_info)."""
    bill = get_bill(apn)
    if not bill:
        return None
    # Fetch the raw county parcel row
    r = get_client().table("parcels").select("row_json").eq("apn", apn).limit(1).execute()
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


def _extract_lat_lng_from_row_json(row_json: str | dict | None) -> tuple[float | None, float | None]:
    """Thin adapter over geo_utils.derive_latlng that keeps this module's
    (lat, lng) | (None, None) tuple contract for existing callers."""
    latlng = derive_latlng(row_json)
    return latlng if latlng is not None else (None, None)


def _normalize_list_apns(apns: list[str], existing_apns: set[str] | None = None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    existing_lookup = existing_apns or set()
    for raw_apn in apns:
        apn = str(raw_apn or "").strip()
        if not apn or apn in seen:
            continue
        if existing_lookup and apn not in existing_lookup:
            continue
        cleaned.append(apn)
        seen.add(apn)
    return cleaned


def _fetch_list_property_context(list_id: int) -> list[dict[str, Any]]:
    lp = (
        get_client()
        .table("list_properties")
        .select("apn, sort_order")
        .eq("list_id", list_id)
        .order("sort_order")
        .execute()
    )
    rows = lp.data or []
    if not rows:
        return []

    apns = [str(row["apn"]) for row in rows if row.get("apn")]
    if not apns:
        return []

    bills = (
        get_client()
        .table("bills")
        .select(
            "apn, location_of_property, city, has_vpt, condition_score, streetview_image_path, power_status, delinquent, deceased_count"
        )
        .in_("apn", apns)
        .execute()
    )
    bill_map = {b["apn"]: b for b in (bills.data or []) if b.get("apn")}
    parcel_rows = (
        get_client()
        .table("parcels")
        .select("apn, row_json")
        .in_("apn", apns)
        .execute()
    )
    parcel_map = {
        row.get("apn"): row.get("row_json")
        for row in (parcel_rows.data or [])
        if row.get("apn")
    }

    favorites = set(get_favorites_apns())
    out: list[dict[str, Any]] = []
    for queue_position, row in enumerate(rows):
        apn = str(row.get("apn") or "").strip()
        if not apn:
            continue
        bill = bill_map.get(apn, {})
        row_json = parcel_map.get(apn)
        lat, lng = _extract_lat_lng_from_row_json(row_json)
        parcel = row_json if isinstance(row_json, dict) else _parse_row_json_value(row_json)
        badges = []
        if bill.get("has_vpt") in (1, True, "1"):
            badges.append("VPT")
        if bill.get("power_status"):
            badges.append(f"Power {str(bill.get('power_status')).upper()}")
        if bill.get("delinquent") in (1, True, "1"):
            badges.append("Delinquent")
        if apn in favorites:
            badges.append("Favorite")

        out.append({
            "apn": apn,
            "sort_order": row.get("sort_order"),
            "queue_position": queue_position,
            "location_of_property": bill.get("location_of_property") or "",
            "address": bill.get("location_of_property") or "",
            "city": bill.get("city") or parcel.get("SitusCity") or "",
            "has_vpt": bill.get("has_vpt") in (1, True, "1"),
            "condition_score": bill.get("condition_score"),
            "streetview_image_path": bill.get("streetview_image_path") or "",
            "power_status": (bill.get("power_status") or "").upper(),
            "is_favorite": apn in favorites,
            "latitude": lat,
            "longitude": lng,
            "lat": lat,
            "lng": lng,
            "row_json": row_json,
            "badges": badges,
        })
    return out


def get_list_properties(list_id: int) -> list[dict]:
    return _fetch_list_property_context(list_id)


def append_properties_to_list(list_id: int, apns: list[str]) -> int:
    return add_properties_to_list(list_id, apns)


def add_properties_to_list(list_id: int, apns: list[str]) -> int:
    """Add a list of APNs to a list. Returns number added (skips already present)."""
    if not apns:
        return 0
    existing = get_client().table("list_properties").select("apn").eq("list_id", list_id).execute()
    existing_apns = {str(row["apn"]) for row in (existing.data or []) if row.get("apn")}
    max_order_r = (
        get_client()
        .table("list_properties")
        .select("sort_order")
        .eq("list_id", list_id)
        .order("sort_order", desc=True)
        .limit(1)
        .execute()
    )
    sort_order = (max_order_r.data[0]["sort_order"] + 1) if max_order_r.data else 0
    added = 0
    next_sort_order = sort_order
    for raw_apn in apns:
        apn = str(raw_apn or "").strip()
        if not apn or apn in existing_apns:
            continue
        get_client().table("list_properties").upsert({"list_id": list_id, "apn": apn, "sort_order": next_sort_order}, on_conflict="list_id,apn").execute()
        existing_apns.add(apn)
        added += 1
        next_sort_order += 1
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
    apns = [str(r["apn"]) for r in rows if r.get("apn")]
    return add_properties_to_list(list_id, apns)


def remove_property_from_list(list_id: int, apn: str) -> bool:
    r = get_client().table("list_properties").delete().eq("list_id", list_id).eq("apn", apn).execute()
    return bool(r.data)


def reorder_list_properties(list_id: int, apns: list[str]) -> int:
    if not apns:
        return 0

    current_rows = (
        get_client()
        .table("list_properties")
        .select("apn, sort_order")
        .eq("list_id", list_id)
        .order("sort_order")
        .execute()
    )
    current = [str(row["apn"]) for row in (current_rows.data or []) if row.get("apn")]
    if not current:
        return 0

    current_set = set(current)
    requested = _normalize_list_apns([str(apn) for apn in apns], existing_apns=current_set)
    if not requested:
        return 0

    ordered: list[str] = []
    seen: set[str] = set()
    for apn in requested:
        if apn in current_set and apn not in seen:
            ordered.append(apn)
            seen.add(apn)
    for apn in current:
        if apn not in seen:
            ordered.append(apn)
            seen.add(apn)

    updated = 0
    for sort_order, apn in enumerate(ordered):
        get_client().table("list_properties").upsert({"list_id": list_id, "apn": apn, "sort_order": sort_order}, on_conflict="list_id,apn").execute()
        updated += 1
    return updated


def get_list_route_waypoints(list_id: int) -> list[dict]:
    return [
        {"lat": stop["lat"], "lng": stop["lng"], "address": stop["address"]}
        for stop in get_list_route_preview(list_id)["stops"]
    ]


def get_list_route_preview(list_id: int) -> dict[str, Any]:
    """Return ordered route preview data for a list."""
    stops = []
    for row in _fetch_list_property_context(list_id):
        if row.get("latitude") is None or row.get("longitude") is None:
            continue
        stops.append(
            {
                "apn": row["apn"],
                "queue_position": row.get("queue_position"),
                "address": row.get("address") or "",
                "city": row.get("city") or "",
                "lat": row.get("latitude"),
                "lng": row.get("longitude"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "has_vpt": row.get("has_vpt", False),
                "condition_score": row.get("condition_score"),
                "streetview_image_path": row.get("streetview_image_path") or "",
                "power_status": row.get("power_status") or "",
                "is_favorite": row.get("is_favorite", False),
                "badges": row.get("badges", []),
            }
        )
    return {"list_id": list_id, "total": len(stops), "stops": stops}


# ---------------------------------------------------------------------------
# Scouting (lists, list_properties, scout_results)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Scouting collections.
#
# `scouting_collections` and `collection_properties` no longer exist: they were
# a second, parallel copy of lists/list_properties, dead on the Kotlin side
# (Repositories.kt already aliases Collection -> List) and dropped in the
# 2026-08-07 baseline schema. These functions keep the /api/scout/collections
# route shape working while delegating to the single lists implementation.
#
# scout_results.collection_id likewise became scout_results.list_id, and
# follow_up / flyered are real booleans now rather than 0/1 integers.
# ---------------------------------------------------------------------------


def get_scout_collections() -> list[dict]:
    out = []
    for row in get_lists():
        scouted = (
            get_client()
            .table("scout_results")
            .select("apn", count="exact")
            .eq("list_id", row["id"])
            .execute()
        )
        out.append({**row, "scouted_count": scouted.count or 0})
    return out


def create_scout_collection(name: str, description: str | None = None, apns: list[str] | None = None) -> int:
    list_id = create_list(name, description)
    if apns:
        add_properties_to_list(list_id, apns)
    return list_id


def delete_scout_collection(collection_id: int) -> bool:
    return delete_list(collection_id)


def get_collection_properties(collection_id: int) -> list[dict]:
    return get_list_properties(collection_id)


def add_properties_to_collection(collection_id: int, apns: list[str]) -> int:
    return add_properties_to_list(collection_id, apns)


def remove_property_from_collection(collection_id: int, apn: str) -> bool:
    return remove_property_from_list(collection_id, apn)


def get_scout_results(collection_id: int | None = None) -> list[dict]:
    q = get_client().table("scout_results").select(
        "id, apn, list_id, follow_up, flyered, notes, scouted_at, latitude, longitude"
    )
    if collection_id is not None:
        q = q.eq("list_id", collection_id)
    r = q.order("scouted_at", desc=True).execute()
    return r.data or []


def upsert_scout_result(
    apn: str,
    collection_id: int | None = None,
    follow_up: int = 0,
    flyered: int = 0,
    notes: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int:
    payload: dict[str, Any] = {
        "apn": apn,
        # Callers still pass 0/1; the columns are boolean.
        "follow_up": bool(follow_up),
        "flyered": bool(flyered),
        "notes": notes or "",
        "latitude": latitude,
        "longitude": longitude,
    }
    if collection_id is not None:
        payload["list_id"] = collection_id
    r = get_client().table("scout_results").insert(payload).execute()
    if r.data and len(r.data) > 0:
        return int(r.data[0]["id"])
    return 0


def get_scout_stats() -> dict:
    total = get_client().table("scout_results").select("id", count="exact").execute()
    follow_ups = get_client().table("scout_results").select("id", count="exact").eq("follow_up", True).execute()
    flyered = get_client().table("scout_results").select("id", count="exact").eq("flyered", True).execute()
    distinct = get_client().table("scout_results").select("apn").execute()
    return {
        "total": total.count or 0,
        "follow_ups": follow_ups.count or 0,
        "flyered": flyered.count or 0,
        "unique_properties": len({row["apn"] for row in (distinct.data or [])}),
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


def get_distinct_zips() -> list[str]:
    """Fetch distinct zip codes from parcels."""
    r = get_client().rpc("get_distinct_zips").execute()
    data = r.data
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "distinct_zip" in data[0]:
        return [row["distinct_zip"] for row in data]
    elif isinstance(data, list) and all(isinstance(x, str) for x in data):
        return data
    return []


def get_distinct_cities() -> list[str]:
    """Fetch distinct normalized city names from bills."""
    cities: set[str] = set()
    offset = 0
    page_size = 1000
    while True:
        r = (
            get_client()
            .table("bills")
            .select("city")
            .not_.is_("city", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = r.data or []
        for row in rows:
            city = str(row.get("city") or "").strip().lstrip("_ ").upper()
            if city:
                cities.add(city)
        if len(rows) < page_size:
            break
        offset += page_size
    return sorted(cities)


def update_property_notes(apn: str, important_notes: str) -> None:
    data: dict[str, Any] = {"important_notes": important_notes}
    get_client().table("bills").update(data).eq("apn", apn).execute()


def update_bill_fields(apn: str, fields: dict[str, Any]) -> None:
    """Update arbitrary allowed fields on a bills row."""
    if not fields:
        return
    get_client().table("bills").update(fields).eq("apn", apn).execute()
