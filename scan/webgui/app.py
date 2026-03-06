#!/usr/bin/env python3
# pyre-ignore-all-errors
from __future__ import annotations

import json
import math
import os
import sys
import html
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, cast

from urllib.parse import quote_plus, urlsplit

# pyre-ignore[21]: Could not find import
from flask import Flask, render_template, request, send_from_directory, jsonify, redirect, url_for, session
# pyre-ignore[21]
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent.parent
BANDOS_DIR = BASE_DIR / "bandos"

# Add project root to path so we can import run_all, db, and other modules
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Use project db: root app.py may have preloaded it; else load from BASE_DIR/db.py, or db_impl.py (same dir), or webgui.db
_WEBGUI_DIR = Path(__file__).resolve().parent
db: Any = cast(Any, type("DB", (), {}))
_db_load_error = None
try:
    if "db" in sys.modules and hasattr(sys.modules["db"], "get_client"):
        db = cast(Any, sys.modules["db"])
    if not hasattr(db, "get_client") and (BASE_DIR / "db.py").exists():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("db", BASE_DIR / "db.py")
        if _spec and _spec.loader:
            _m = importlib.util.module_from_spec(_spec)
            sys.modules["db"] = _m
            # pyre-ignore[16]
            _spec.loader.exec_module(_m)
            if hasattr(_m, "get_client"):
                db = cast(Any, _m)
    if not hasattr(db, "get_client") and (_WEBGUI_DIR / "db_impl.py").exists():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("db", _WEBGUI_DIR / "db_impl.py")
        if _spec and _spec.loader:
            _m = importlib.util.module_from_spec(_spec)
            sys.modules["db"] = _m
            # pyre-ignore[16]
            _spec.loader.exec_module(_m)
            if hasattr(_m, "get_client"):
                db = cast(Any, _m)
    if not hasattr(db, "get_client"):
        # pyre-ignore[21]
        import webgui.db as fallback_db
        sys.modules["db"] = fallback_db
        db = cast(Any, fallback_db)
except Exception as e:
    _db_load_error = e
    class _DbStub:
        def __getattr__(self, name: str) -> Any:
            raise RuntimeError(f"db failed to load: {_db_load_error}")
    from typing import cast
    db = cast(Any, _DbStub())

# API key for mobile/Scout app access (unchanged)
# Load .env file
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

SCOUT_API_KEY = os.environ.get("SCOUT_API_KEY", "")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vpt-local-secret-key-change-me")

_TRANSIENT_NETWORK_ERROR_NAMES = {
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
}
_TRANSIENT_NETWORK_ERROR_MARKERS = (
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
        next_exc = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        current = next_exc if isinstance(next_exc, BaseException) else None


def _is_transient_upstream_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if current.__class__.__name__ in _TRANSIENT_NETWORK_ERROR_NAMES:
            return True
        msg = str(current).lower()
        if any(marker in msg for marker in _TRANSIENT_NETWORK_ERROR_MARKERS):
            return True
    return False


def _supabase_configured() -> bool:
    """Return True if Supabase env vars are set (for Vercel/serverless)."""
    url = os.environ.get("SUPABASE_URL", "")
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY", "")
    )
    return bool(url and key)


@app.errorhandler(RuntimeError)
def handle_runtime_error(e: RuntimeError):
    """Return clear 503 when Supabase is not configured (e.g. missing Vercel env vars)."""
    msg = str(e).lower()
    if "supabase" in msg or "supabase_url" in msg or "supabase_anon_key" in msg or ".env" in msg:
        body = (
            "<!DOCTYPE html><html><head><title>Configuration required</title></head><body>"
            "<h1>Configuration required</h1><p>Supabase is not configured. On Vercel, set these "
            "<strong>Environment Variables</strong> in your project:</p><ul>"
            "<li><code>SUPABASE_URL</code> – your Supabase project URL</li>"
            "<li><code>SUPABASE_ANON_KEY</code> or <code>SUPABASE_SERVICE_KEY</code> – your Supabase key</li>"
            "</ul><p>Optional: <code>SECRET_KEY</code> (session cookie), <code>SCOUT_API_KEY</code> (mobile)</p>"
            "</body></html>"
        )
        return body, 503, {"Content-Type": "text/html; charset=utf-8"}
    return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


@app.errorhandler(Exception)
def handle_unhandled(e: Exception):
    """Return 500 with error details so we can debug (e.g. on Vercel)."""
    if isinstance(e, HTTPException):
        return e
    if _is_transient_upstream_error(e):
        return jsonify(
            error="Upstream Service Unavailable",
            message="Temporary upstream connection issue. Please retry.",
            type=type(e).__name__,
        ), 503
    return jsonify(
        error="Internal Server Error",
        message=str(e),
        type=type(e).__name__,
    ), 500


@app.route("/ping")
def ping():
    """Minimal route without db to verify app starts."""
    return "pong", 200, {"Content-Type": "text/plain"}


@app.route("/health")
def health():
    """Health check for Vercel/deployments. No auth. Returns 200 if app is up, db status in body."""
    try:
        if _supabase_configured():
            db.get_client()
            return jsonify({"status": "ok", "db": "connected"})
        return jsonify({"status": "degraded", "db": "not_configured", "hint": "Set SUPABASE_URL and SUPABASE_ANON_KEY in Vercel Environment Variables"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 503


def _get_claims_from_token(token: str) -> dict | None:
    """Verify Supabase JWT and return claims dict (sub, email, ...) or None."""
    if not _supabase_configured():
        return None
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    # 1) Try get_claims(jwt=...) if available (supabase-py 2.x)
    try:
        client = db.get_client()
        if hasattr(client.auth, "get_claims"):
            resp = client.auth.get_claims(jwt=token)
            if hasattr(resp, "claims") and resp.claims:
                c = resp.claims
                claims = c if isinstance(c, dict) else (getattr(c, "model_dump")() if hasattr(c, "model_dump") else None)
                if isinstance(claims, dict) and claims.get("sub"):
                    return claims
            if hasattr(resp, "model_dump"):
                data = resp.model_dump()
                if isinstance(data.get("claims"), dict) and data["claims"].get("sub"):
                    return data["claims"]
    except Exception:
        pass
    # 2) Fallback: GET /auth/v1/user with Bearer token
    if url and anon:
        try:
            # pyre-ignore[21]
            import requests
            resp = requests.get(
                f"{url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": anon},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("id") and data
                if user:
                    return {"sub": user.get("id"), "email": user.get("email") or ""}
        except Exception:
            pass
    return None


def _verify_supabase_session() -> dict | None:
    """Verify session's Supabase JWT and return claims dict if valid, else None."""
    token = session.get("supabase_access_token")
    if not token or not _supabase_configured():
        return None
    return _get_claims_from_token(token)


def _verify_supabase_bearer_request() -> dict | None:
    """Verify Authorization: Bearer <jwt> from request headers."""
    if not _supabase_configured():
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    return _get_claims_from_token(token)


def login_required(f):
    """Require Supabase auth (session or bearer token) or SCOUT_API_KEY."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Scout/mobile: API key in header or query
        if SCOUT_API_KEY:
            api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
            if api_key and api_key == SCOUT_API_KEY:
                return f(*args, **kwargs)

        # Mobile/API: Supabase Auth bearer token
        claims = _verify_supabase_bearer_request()
        if claims:
            return f(*args, **kwargs)

        # Web UI: Supabase Auth session
        claims = _verify_supabase_session()
        if not claims:
            session.pop("supabase_access_token", None)
            session.pop("user_id", None)
            session.pop("user_email", None)
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        # Keep session claims in sync for templates
        session["user_id"] = claims.get("sub")
        session["user_email"] = claims.get("email") or session.get("user_email") or "User"
        return f(*args, **kwargs)
    return decorated_function



@app.route("/login", methods=["GET"])
def login():
    """Login page – auth is handled by Supabase Auth on the client."""
    if _verify_supabase_session():
        return redirect(url_for("search_page"))
    return render_template(
        "login.html",
        error=request.args.get("error"),
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
    )


@app.route("/auth/callback", methods=["POST"])
def auth_callback():
    """Accept Supabase access_token from client, verify, and create session."""
    if not _supabase_configured():
        return jsonify({"error": "Supabase not configured"}), 503
    data = request.get_json(silent=True) or {}
    token = (data.get("access_token") or "").strip()
    if not token:
        return jsonify({"error": "Missing access_token"}), 400
    claims = _get_claims_from_token(token)
    if not claims or not claims.get("sub"):
        return jsonify({"error": "Invalid or expired token"}), 401
    session["supabase_access_token"] = token
    session["user_id"] = claims.get("sub")
    session["user_email"] = claims.get("email") or "User"
    return jsonify({"ok": True, "redirect": url_for("search_page")})


@app.route("/logout")
def logout():
    """Logout and clear session."""
    session.pop("supabase_access_token", None)
    session.pop("user_id", None)
    session.pop("user_email", None)
    return redirect(url_for("login"))


def web_mercator_to_latlng(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) to WGS84 lat/lng."""
    lng = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return lat, lng
@app.route("/pdf/<path:filename>")
@login_required
def pdf(filename: str):
    return send_from_directory(BANDOS_DIR, filename, as_attachment=False)




def parse_row_json(row_json: str | dict | None) -> dict[str, Any]:
    if not row_json:
        return {}
    if isinstance(row_json, dict):
        return row_json
    try:
        return json.loads(row_json)
    except json.JSONDecodeError:
        return {}


def _safe_return_to(raw: str | None, fallback: str = "/") -> str:
    """Allow only local relative paths for in-app back navigation."""
    if not raw:
        return fallback
    value = raw.strip()
    if not value.startswith("/") or value.startswith("//"):
        return fallback
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return fallback
    return value


@app.route("/")
@login_required
def home():
    """Dashboard home page."""
    return render_template("home.html", active_nav="home")


@app.route("/search")
@login_required
def search_page():
    q = (request.args.get("q") or "").strip()
    zip_list = request.args.getlist("zip")
    zip_filter = ",".join(item.strip() for sub in zip_list for item in sub.split(",") if item.strip())
    power_filter = (request.args.get("power") or "").strip()
    fav_filter = (request.args.get("fav") or "").strip()
    city_filter = (request.args.get("city") or "").strip().upper()
    vpt_filter = (request.args.get("vpt") or "").strip()
    delinquent_filter = (request.args.get("delinquent") or "").strip()
    condition_filter = (request.args.get("condition") or "").strip()
    outofstate_filter = (request.args.get("outofstate") or "").strip()
    research_filter = (request.args.get("research") or "").strip()
    occupancy_filter = (request.args.get("occupancy_type") or "").strip()
    ownership_filter = (request.args.get("ownership_type") or "").strip()
    primary_resident_age_filter = (request.args.get("primary_resident_age") or "").strip()
    deceased_count_filter = (request.args.get("deceased_count") or "").strip()
    outreach_stage_filter = (request.args.get("outreach_stage") or "").strip()
    owner_name_filter = (request.args.get("owner_name") or "").strip()
    sort = request.args.get("sort") or "location_of_property"
    order = request.args.get("order") or "asc"
    page = max(int(request.args.get("page") or 1), 1)
    page_size = min(max(int(request.args.get("page_size") or 25), 10), 200)

    allowed_sorts = {
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
        "primary_resident_age",
        "deceased_count",
        "outreach_score",
    }
    if sort not in allowed_sorts:
        sort = "location_of_property"
    order = "desc" if order.lower() == "desc" else "asc"

    favorites_set = set(db.get_favorites_apns())
    rows, total = db.get_bills_with_parcels_filtered(
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

    # Post-filter by outreach stage if requested
    if outreach_stage_filter:
        stage_val = outreach_stage_filter.lower().replace(" ", "_")
        rows = [r for r in rows if (r.get("outreach_stage") or "identified") == stage_val]
        total = len(rows)

    # Build display rows with some parcel fields pulled from JSON
    display = []
    for r in rows:
        parcel = parse_row_json(r["row_json"])
        power = r["power_status"] or ""
        apn = r["apn"]
        display.append(
            {
                "pdf_file": r["pdf_file"],
                "bill_url": r["bill_url"] or "",
                "apn": apn,
                "parcel_number": r["parcel_number"],
                "tracer_number": r["tracer_number"],
                "location_of_property": r["location_of_property"],
                "tax_year": r["tax_year"],
                "last_payment": r["last_payment"] or "",
                "delinquent": "Yes" if (r["delinquent"] or 0) == 1 else "No",
                "power_status": power.upper() if power else "",
                "has_vpt": "Yes" if (r["has_vpt"] or 0) == 1 else "No",
                "vpt_marker": r["vpt_marker"] or "",
                "city": r["city"] or parcel.get("SitusCity") or "",
                "is_favorite": apn in favorites_set,
                "mailing_address": parcel.get("MailingAddress") or "",
                "situs_address": parcel.get("SitusAddress") or "",
                "situs_city": parcel.get("SitusCity") or "",
                "situs_zip": r["situs_zip"] or "",
                "pdf_url": f"/pdf/{r['pdf_file']}" if r["pdf_file"] else "",
                "bill_url": r["bill_url"] or "",
                "maps_url": (
                    f"https://www.google.com/maps/search/?api=1&query="
                    f"{quote_plus(r['location_of_property'] or '')}"
                    if r["location_of_property"]
                    else ""
                ),
                "condition_score": r["condition_score"],
                "condition_notes": r["condition_notes"] or "",
                "streetview_image_path": r["streetview_image_path"] or "",
                "property_search_url": r.get("property_search_url") or "",
                "mailing_search_url": r.get("mailing_search_url") or "",
                "prop_occupancy_type": r.get("prop_occupancy_type") or "",
                "prop_ownership_type": r.get("prop_ownership_type") or "",
                "prop_last_sale_date": r.get("prop_last_sale_date") or "",
                "primary_resident_name": r.get("primary_resident_name") or "",
                "primary_resident_age": r.get("primary_resident_age") or "",
                "primary_resident_phone_number": r.get("owner_mobile_phone") or "",
                "deceased_count": r.get("deceased_count"),
                "important_notes": r.get("important_notes") or "",
                "outreach_score": r.get("outreach_score"),
                "outreach_stage": r.get("outreach_stage") or "",
                "owner_name": r.get("owner_name") or "",
            }
        )

    total_pages = max((int(total) + int(page_size) - 1) // int(page_size), 1)
    return_to_path = request.full_path if request.query_string else request.path

    return render_template(
        "index.html",
        active_nav="search",
        rows=display,
        return_to_path=return_to_path,
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
        occupancy_filter=occupancy_filter,
        ownership_filter=ownership_filter,
        primary_resident_age_filter=primary_resident_age_filter,
        deceased_count_filter=deceased_count_filter,
        outreach_stage_filter=outreach_stage_filter,
        owner_name_filter=owner_name_filter,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        available_zips=db.get_distinct_zips(),
    )


@app.route("/api/apn_list")
@login_required
def api_apn_list():
    """Return [{apn, address}, ...] for the current filter state (all pages)."""
    q = (request.args.get("q") or "").strip()
    zip_list = request.args.getlist("zip")
    zip_filter = ",".join(item.strip() for sub in zip_list for item in sub.split(",") if item.strip())
    power_filter = (request.args.get("power") or "").strip()
    fav_filter = (request.args.get("fav") or "").strip()
    city_filter = (request.args.get("city") or "").strip().upper()
    vpt_filter = (request.args.get("vpt") or "").strip()
    delinquent_filter = (request.args.get("delinquent") or "").strip()
    condition_filter = (request.args.get("condition") or "").strip()
    outofstate_filter = (request.args.get("outofstate") or "").strip()
    research_filter = (request.args.get("research") or "").strip()
    owner_name_filter = (request.args.get("owner_name") or "").strip()
    outreach_stage_filter = (request.args.get("outreach_stage") or "").strip()
    sort = request.args.get("sort") or "location_of_property"
    order = request.args.get("order") or "asc"

    allowed_sorts = {
        "location_of_property", "apn", "parcel_number", "tracer_number",
        "tax_year", "pdf_file", "situs_zip", "last_payment", "delinquent",
        "power_status", "city", "has_vpt", "condition_score",
        "primary_resident_age", "deceased_count", "outreach_score",
    }
    if sort not in allowed_sorts:
        sort = "location_of_property"
    order = "desc" if order.lower() == "desc" else "asc"

    rows, _ = db.get_bills_with_parcels_filtered(
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
        page=1,
        page_size=0,  # 0 = unlimited
    )

    if outreach_stage_filter:
        stage_val = outreach_stage_filter.lower().replace(" ", "_")
        rows = [r for r in rows if (r.get("outreach_stage") or "identified") == stage_val]

    return jsonify([
        {"apn": r["apn"], "address": r.get("location_of_property") or r["apn"]}
        for r in rows
    ])


@app.route("/property/<path:apn>")
@login_required
def property_detail(apn: str):
    """Property detail page with street view image, edit modal, and research links."""
    row = db.get_bill_with_parcel(apn)
    if not row:
        return jsonify({"error": "Property not found"}), 404

    parcel = parse_row_json(row.get("row_json"))
    location = row.get("location_of_property") or parcel.get("SitusAddress") or apn
    city = row.get("city") or parcel.get("SitusCity") or ""
    power_status = (row.get("power_status") or "").upper()
    pdf_file = row.get("pdf_file") or ""
    pdf_url = f"/pdf/{pdf_file}" if pdf_file else ""
    streetview_maps_url = (
        f"https://www.google.com/maps/search/?api=1&query={quote_plus(location)}"
        if location else ""
    )
    tax_bill_url = f"https://propertytax.alamedacountyca.gov/account-summary?apn={quote_plus(apn)}"

    links: list[dict[str, str]] = []
    property_search_url = row.get("property_search_url") or ""
    if property_search_url:
        label = "CBC Property Search" if "cyberbackgroundchecks.com" in property_search_url.lower() else "Property Search"
        links.append({"label": label, "url": property_search_url})

    mailing_search_url = row.get("mailing_search_url") or ""
    if mailing_search_url:
        label = "CBC Mailing Search" if "cyberbackgroundchecks.com" in mailing_search_url.lower() else "Mailing Search"
        links.append({"label": label, "url": mailing_search_url})

    owner_details_url = row.get("owner_details_url") or ""
    if owner_details_url:
        links.append({"label": "Owner Details", "url": owner_details_url})

    # Always include tax bill link using APN-specific account-summary URL
    links.append({"label": "Property Tax Bill", "url": tax_bill_url})

    if pdf_url:
        links.append({"label": "Bill PDF", "url": pdf_url})
    if row.get("research_report_path"):
        links.append({"label": "Research Report", "url": url_for("property_research_report", apn=apn)})
    if row.get("condition_score") is not None or row.get("condition_notes"):
        links.append({"label": "Condition Report", "url": url_for("property_condition_report", apn=apn)})
    # Google Maps link removed (street view image replaces it)

    return_to = _safe_return_to(request.args.get("return_to"), fallback=url_for("search_page"))
    property_data = {
        "apn": apn,
        "display_name": location,
        "location_of_property": location,
        "city": city,
        "parcel_number": row.get("parcel_number") or "",
        "tracer_number": row.get("tracer_number") or "",
        "tax_year": row.get("tax_year") or "",
        "last_payment": row.get("last_payment") or "",
        "delinquent": "Yes" if (row.get("delinquent") or 0) == 1 else "No",
        "power_status": power_status or "-",
        "has_vpt": "Yes" if (row.get("has_vpt") or 0) == 1 else "No",
        "condition_score": row.get("condition_score"),
        "condition_notes": row.get("condition_notes") or "",
        "owner_name": row.get("owner_name") or "",
        "important_notes": row.get("important_notes") or "",
        "mailing_address": parcel.get("MailingAddress") or "",
        "situs_address": parcel.get("SitusAddress") or "",
        "situs_city": parcel.get("SitusCity") or "",
        "situs_zip": row.get("situs_zip") or "",
        "research_status": row.get("research_status") or "unchecked",
        "has_report": bool(row.get("research_report_path")),
        "pdf_url": pdf_url,
        "bill_url": row.get("bill_url") or "",
        "streetview_image_path": row.get("streetview_image_path") or "",
        "is_favorite": db.has_favorite(apn),
        "owner_email": row.get("owner_email") or "",
        "owner_phone": row.get("owner_phone") or "",
        "outreach_stage": row.get("outreach_stage") or "identified",
        "prop_occupancy_type": row.get("prop_occupancy_type") or "",
        "prop_ownership_type": row.get("prop_ownership_type") or "",
        "primary_resident_name": row.get("primary_resident_name") or "",
        "primary_resident_age": row.get("primary_resident_age") or "",
        "deceased_count": row.get("deceased_count"),
        "prop_last_sale_date": row.get("prop_last_sale_date") or "",
        "streetview_maps_url": streetview_maps_url,
        "tax_bill_url": tax_bill_url,
    }

    return render_template(
        "property.html",
        property=property_data,
        links=links,
        return_to=return_to,
        active_nav="search",
    )


@app.route("/property/<path:apn>/research-report")
@login_required
def property_research_report(apn: str):
    """Render research report as embeddable HTML for in-app viewer."""
    try:
        # pyre-ignore[21]
        import scanner.gemini_research_scanner as grs
        report = grs.get_research_report(apn)
    except Exception as e:
        return f"<h2>Research Report Error</h2><p>{html.escape(str(e))}</p>", 500

    if not report:
        return "<h2>Research Report</h2><p>No report found for this property.</p>", 404

    escaped_report = html.escape(report)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Research Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:16px;line-height:1.55;color:#111;}"
        "h1{font-size:20px;margin:0 0 10px 0;} pre{white-space:pre-wrap;word-break:break-word;"
        "background:#f8fafc;border:1px solid #dbe5f0;padding:12px;border-radius:8px;}"
        "</style></head><body>"
        f"<h1>Research Report: {html.escape(apn)}</h1>"
        f"<pre>{escaped_report}</pre>"
        "</body></html>"
    )


@app.route("/property/<path:apn>/condition-report")
@login_required
def property_condition_report(apn: str):
    """Render condition details as embeddable HTML for in-app viewer."""
    bill = db.get_bill(apn)
    if not bill:
        return "<h2>Condition Report</h2><p>Property not found.</p>", 404

    score = bill.get("condition_score")
    notes = bill.get("condition_notes") or "No condition notes saved."
    updated_at = bill.get("condition_updated_at") or "Unknown"
    image_tag = (
        f"<img src='{url_for('api_streetview_image', apn=apn)}' alt='Street View' "
        "style='max-width:100%;border-radius:8px;border:1px solid #dbe5f0;margin:10px 0;'>"
        if bill.get("streetview_image_path")
        else ""
    )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Condition Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:16px;line-height:1.55;color:#111;}"
        "h1{font-size:20px;margin:0 0 10px 0;} .meta{color:#5f6c7b;margin-bottom:10px;}"
        "pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid #dbe5f0;"
        "padding:12px;border-radius:8px;}</style></head><body>"
        f"<h1>Condition Report: {html.escape(apn)}</h1>"
        f"<div class='meta'>Score: {html.escape(str(score)) if score is not None else 'Not Scored'}"
        f" • Updated: {html.escape(str(updated_at))}</div>"
        f"{image_tag}"
        f"<pre>{html.escape(notes)}</pre>"
        "</body></html>"
    )


@app.route("/map")
@login_required
def map_view():
    """Render the map view page."""
    return render_template("map.html", available_zips=db.get_distinct_zips(), active_nav="search")


def _extract_zip_code(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    digits = "".join(ch if ch.isdigit() else " " for ch in text)
    for token in reversed(digits.split()):
        if len(token) == 5:
            return token
    return ""


def _is_truthy_flag(value: Any) -> bool:
    return value in (1, True, "1", "true", "True", "yes", "Yes", "YES")


def _row_matches_map_filters(
    row: dict[str, Any],
    parcel: dict[str, Any],
    *,
    q: str,
    zip_values: set[str],
    power_filter: str,
    fav_filter: str,
    city_filter: str,
    vpt_filter: str,
    delinquent_filter: str,
    owner_name_filter: str,
    favorites_set: set[str],
) -> bool:
    apn = str(row.get("apn") or "").strip()
    location = str(row.get("location_of_property") or "").strip()
    owner_name = str(row.get("owner_name") or "").strip()
    city_value = str(row.get("city") or parcel.get("SitusCity") or "").strip().upper()
    power_value = str(row.get("power_status") or "").strip().upper()

    if q:
        q_norm = q.lower()
        haystack = " ".join(
            [
                apn,
                location,
                str(row.get("parcel_number") or ""),
                str(row.get("tracer_number") or ""),
                city_value,
                owner_name,
                str(parcel.get("SitusAddress") or ""),
                str(parcel.get("MailingAddress") or ""),
            ]
        ).lower()
        if q_norm not in haystack:
            return False

    if zip_values:
        zip_candidates = {
            _extract_zip_code(str(parcel.get("SitusZip") or "")),
            _extract_zip_code(str(parcel.get("MailingZip") or "")),
            _extract_zip_code(location),
        }
        zip_candidates = {z for z in zip_candidates if z}
        if not (zip_candidates & zip_values):
            return False

    normalized_power_filter = (power_filter or "").strip().lower()
    if normalized_power_filter == "on" and power_value != "ON":
        return False
    if normalized_power_filter == "off" and power_value != "OFF":
        return False
    if normalized_power_filter == "unknown" and power_value in {"ON", "OFF"}:
        return False

    if fav_filter == "1" and apn not in favorites_set:
        return False

    if city_filter and city_value != city_filter:
        return False

    if vpt_filter == "1" and not _is_truthy_flag(row.get("has_vpt")):
        return False

    if delinquent_filter == "1" and not _is_truthy_flag(row.get("delinquent")):
        return False

    if owner_name_filter and owner_name_filter.lower() not in owner_name.lower():
        return False

    return True


def _get_list_map_rows(list_id: int) -> list[dict[str, Any]]:
    list_properties = (
        db.get_client()
        .table("list_properties")
        .select("apn, sort_order")
        .eq("list_id", list_id)
        .order("sort_order")
        .execute()
    )
    list_apns = [str(row.get("apn") or "").strip() for row in (list_properties.data or []) if row.get("apn")]
    if not list_apns:
        return []

    bills = _chunked_in_query(
        "bills",
        ",".join(
            [
                "apn",
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
                "bill_url",
                "property_search_url",
                "mailing_search_url",
                "condition_score",
                "owner_name",
            ]
        ),
        "apn",
        list_apns,
    )
    parcels = _chunked_in_query("parcels", "APN, row_json", "APN", list_apns)

    bill_by_apn = {str(row.get("apn")): row for row in bills if row.get("apn")}
    parcel_json_by_apn = {str(row.get("APN")): row.get("row_json") for row in parcels if row.get("APN")}

    rows: list[dict[str, Any]] = []
    for apn in list_apns:
        bill = bill_by_apn.get(apn)
        if not bill:
            continue
        row = dict(bill)
        row["row_json"] = parcel_json_by_apn.get(apn)
        rows.append(row)
    return rows


@app.route("/api/markers")
@login_required
def api_markers():
    """Return all entries as GeoJSON for the map."""
    # Get filter parameters
    q = (request.args.get("q") or "").strip()
    zip_list = request.args.getlist("zip")
    zip_filter = ",".join(item.strip() for sub in zip_list for item in sub.split(",") if item.strip())
    power_filter = (request.args.get("power") or "").strip()
    fav_filter = (request.args.get("fav") or "").strip()
    city_filter = (request.args.get("city") or "").strip().upper()
    vpt_filter = (request.args.get("vpt") or "").strip()
    delinquent_filter = (request.args.get("delinquent") or "").strip()
    owner_name_filter = (request.args.get("owner_name") or "").strip()
    list_id_raw = (request.args.get("list_id") or "").strip()
    try:
        page = max(int(request.args.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(int(request.args.get("page_size") or 200), 50), 200)
    except (TypeError, ValueError):
        page_size = 200

    favorites_set = set(db.get_favorites_apns())
    rows: list[dict[str, Any]]
    total: int

    if list_id_raw:
        try:
            list_id = int(list_id_raw)
        except ValueError:
            return jsonify({"error": "Invalid list_id"}), 400
        if not db.get_list(list_id):
            return jsonify({"error": "List not found"}), 404

        list_rows = _get_list_map_rows(list_id)
        zip_values = {item.strip() for item in zip_filter.split(",") if item.strip()}
        filtered_rows: list[dict[str, Any]] = []
        for row in list_rows:
            parcel = parse_row_json(row.get("row_json"))
            if not _row_matches_map_filters(
                row,
                parcel,
                q=q,
                zip_values=zip_values,
                power_filter=power_filter,
                fav_filter=fav_filter,
                city_filter=city_filter,
                vpt_filter=vpt_filter,
                delinquent_filter=delinquent_filter,
                owner_name_filter=owner_name_filter,
                favorites_set=favorites_set,
            ):
                continue
            filtered_rows.append(row)

        total = len(filtered_rows)
        start = (page - 1) * page_size
        rows = filtered_rows[start : start + page_size]
    else:
        rows, total = db.get_bills_with_parcels_filtered(
            q=q,
            zip_filter=zip_filter,
            power_filter=power_filter,
            fav_filter=fav_filter,
            city_filter=city_filter,
            vpt_filter=vpt_filter,
            delinquent_filter=delinquent_filter,
            condition_filter="",
            outofstate_filter="",
            research_filter="",
            owner_name_filter=owner_name_filter,
            sort="location_of_property",
            order="asc",
            page=page,
            page_size=page_size,
        )

    markers = []
    for r in rows:
        parcel = parse_row_json(r["row_json"])
        
        # Get coordinates from parcel data (handle both CSV formats)
        try:
            x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
            y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
        except (ValueError, TypeError):
            x, y = 0, 0
        
        if x == 0 or y == 0:
            continue
        
        lat, lng = web_mercator_to_latlng(x, y)
        
        location = r["location_of_property"] or ""
        power = r["power_status"] or ""
        apn = r["apn"] or ""
        
        markers.append({
            "lat": lat,
            "lng": lng,
            "apn": apn,
            "parcel_number": r["parcel_number"] or "",
            "tracer_number": r["tracer_number"] or "",
            "location": location,
            "tax_year": r["tax_year"] or "",
            "last_payment": r["last_payment"] or "",
            "delinquent": "Yes" if (r["delinquent"] or 0) == 1 else "No",
            "power_status": power.upper() if power else "",
            "has_vpt": "Yes" if (r["has_vpt"] or 0) == 1 else "No",
            "vpt_marker": r["vpt_marker"] or "",
            "city": r["city"] or parcel.get("SitusCity") or "",
            "is_favorite": apn in favorites_set,
            "mailing_address": parcel.get("MailingAddress") or "",
            "situs_address": parcel.get("SitusAddress") or "",
            "property_search_url": r.get("property_search_url") or "",
            "mailing_search_url": r.get("mailing_search_url") or "",
            "bill_url": r["bill_url"] or "",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(location)}" if location else "",
            "streetview_url": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}" if lat and lng else "",
            "condition_score": r["condition_score"],
            "owner_name": r.get("owner_name") or "",
        })

    has_more = (int(page) * int(page_size)) < int(total)
    return jsonify(
        {
            "items": markers,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }
    )


@app.route("/api/favorites", methods=["GET"])
@login_required
def api_favorites_list():
    """Return list of favorite APNs."""
    return jsonify(db.get_favorites_apns())


def _clean_apn(apn: str) -> str:
    return (apn or "").strip()


@app.route("/api/favorites/<path:apn>", methods=["POST"])
@login_required
def api_favorites_add(apn: str):
    """Add an APN to favorites."""
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400
    db.add_favorite(cleaned_apn)
    return jsonify({"status": "ok", "apn": cleaned_apn, "favorited": True})


@app.route("/api/favorites/<path:apn>", methods=["DELETE"])
@login_required
def api_favorites_remove(apn: str):
    """Remove an APN from favorites."""
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400
    db.remove_favorite(cleaned_apn)
    return jsonify({"status": "ok", "apn": cleaned_apn, "favorited": False})


@app.route("/api/favorites/<path:apn>/toggle", methods=["POST"])
@login_required
def api_favorites_toggle(apn: str):
    """Toggle favorite status for an APN."""
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400
    favorited = db.toggle_favorite(cleaned_apn)
    return jsonify({"status": "ok", "apn": cleaned_apn, "favorited": favorited})


@app.route("/api/property/<path:apn>", methods=["DELETE"])
@login_required
def api_property_delete(apn: str):
    """Permanently delete a property from the database."""
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400
    deleted = db.delete_bill(cleaned_apn)
    if not deleted:
        return jsonify({"status": "error", "message": "Property not found"}), 404
    return jsonify({"status": "ok", "apn": cleaned_apn})


@app.route("/api/property/bulk-delete", methods=["POST"])
@login_required
def api_property_bulk_delete():
    """Permanently delete multiple properties from the database."""
    data = request.get_json() or {}
    apns = data.get("apns", [])
    if not apns or not isinstance(apns, list):
        return jsonify({"status": "error", "message": "apns list is required"}), 400
    cleaned = [a for a in (_clean_apn(str(x)) for x in apns) if a]
    if not cleaned:
        return jsonify({"status": "error", "message": "No valid APNs provided"}), 400
    count = db.bulk_delete_bills(cleaned)
    return jsonify({"status": "ok", "deleted": count})


@app.route("/api/favorites/bulk", methods=["POST"])
@login_required
def api_favorites_bulk_add():
    """Add multiple APNs to favorites."""
    data = request.get_json() or {}
    apns = data.get("apns", [])
    if not apns or not isinstance(apns, list):
        return jsonify({"status": "error", "message": "apns list is required"}), 400
    cleaned = [a for a in (_clean_apn(str(x)) for x in apns) if a]
    if not cleaned:
        return jsonify({"status": "error", "message": "No valid APNs provided"}), 400
    count = db.bulk_add_favorites(cleaned)
    return jsonify({"status": "ok", "added": count})


@app.route("/api/properties/<path:apn>/notes", methods=["POST"])
@login_required
def api_update_property_notes(apn: str):
    """Update important notes for a property."""
    data = request.get_json() or {}
    notes = data.get("notes")
    
    if notes is None:
        return jsonify({"status": "error", "message": "Notes field is required"}), 400
        
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400
        
    try:
        db.update_property_notes(cleaned_apn, notes)
        return jsonify({"status": "ok", "message": "Notes updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/properties/<path:apn>/update", methods=["POST"])
@login_required
def api_update_property(apn: str):
    """Update editable fields for a property."""
    allowed_fields = {
        "important_notes", "outreach_stage", "owner_name", "owner_phone",
        "owner_email", "condition_score", "condition_notes",
        "prop_occupancy_type", "prop_ownership_type",
    }
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400

    payload = request.get_json() or {}
    fields = {k: v for k, v in payload.items() if k in allowed_fields}
    if not fields:
        return jsonify({"status": "error", "message": "No valid fields provided"}), 400

    # Coerce condition_score to float if present
    if "condition_score" in fields:
        try:
            val = fields["condition_score"]
            fields["condition_score"] = float(val) if val not in (None, "", "null") else None
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "condition_score must be a number"}), 400

    if "outreach_stage" in fields and fields["outreach_stage"] not in db.OUTREACH_STAGES:
        return jsonify({"status": "error", "message": "Invalid outreach_stage"}), 400

    try:
        db.update_bill_fields(cleaned_apn, fields)
        return jsonify({"status": "ok", "message": "Property updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/scan")
@login_required
def scan_page():
    """Scan control dashboard."""
    return render_template("scan.html", active_nav="scan")


@app.route("/admin")
@login_required
def admin_page():
    """Backward-compatible redirect to /scan."""
    return redirect(url_for("scan_page"))


@app.route("/api/scan/status")
@login_required
def api_scan_status():
    """Get current scan status."""
    try:
        import scanner.run_all as run_all
        status = run_all.get_scan_state()
        
        # Add DB stats
        status["total_bills"] = db.get_bills_count_where()
        status["vpt_count"] = db.get_bills_count_where(has_vpt=1)
        bills = db.get_client().table("bills").select("city").not_.is_("city", "null").execute()
        from collections import Counter
        status["city_counts"] = dict(Counter(row["city"] for row in (bills.data or []) if row.get("city")))
        status["scanner_available"] = True
        
        return jsonify(status)
    except ModuleNotFoundError:
        # Scanner modules not available (e.g. Vercel deployment)
        return jsonify({"is_running": False, "scanner_available": False})
    except Exception as e:
        return jsonify({"error": str(e), "is_running": False, "scanner_available": False})


@app.route("/api/scan/start", methods=["POST"])
@login_required
def api_scan_start():
    """Start a scan."""
    try:
        import scanner.run_all as run_all
        data = request.get_json() or {}
        city = data.get("city")
        continuous = data.get("continuous", False)
        
        if run_all.scan_state["is_running"]:
            return jsonify({"status": "error", "message": "Scan already running"})
        
        success = run_all.start_scan(city=city, continuous=continuous)
        if success:
            return jsonify({"status": "ok", "message": f"Scan started for {city or 'all cities'}"})
        else:
            return jsonify({"status": "error", "message": "Failed to start scan"})
    except ModuleNotFoundError:
        return jsonify({"status": "error", "message": "Scanner not available in cloud deployment"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/scan/stop", methods=["POST"])
@login_required
def api_scan_stop():
    """Stop continuous scan."""
    try:
        import scanner.run_all as run_all
        success = run_all.stop_scan()
        if success:
            return jsonify({"status": "ok", "message": "Scan stopping..."})
        else:
            return jsonify({"status": "error", "message": "Cannot stop (not in continuous mode)"})
    except ModuleNotFoundError:
        return jsonify({"status": "error", "message": "Scanner not available in cloud deployment"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ============================================================================
# Deep Research API Endpoints
# ============================================================================

@app.route("/api/research/status")
@login_required
def api_research_status_all():
    """Get current research scanner status."""
    try:
        import scanner.gemini_research_scanner as gemini_research_scanner
        gemini_research_scanner.ensure_research_columns()
        status = gemini_research_scanner.get_research_state()

        # Add DB stats
        status["total_completed"] = db.get_bills_count_where(research_status="completed")

        # "Pending" = not yet fully researched: NULL or 'unchecked'
        pending_q = (
            db.get_client()
            .table("bills")
            .select("apn", count="exact")
            .or_("research_status.is.null,research_status.eq.unchecked")
        )
        pending_r = pending_q.limit(1).execute()
        status["total_pending"] = pending_r.count or 0

        status["total_failed"] = db.get_bills_count_where(research_status="failed")
        status["scanner_available"] = True

        return jsonify(status)
    except ModuleNotFoundError:
        return jsonify({"is_running": False, "api_configured": False, "scanner_available": False})
    except Exception as e:
        return jsonify({"error": str(e), "is_running": False, "api_configured": False, "scanner_available": False})


@app.route("/api/research/status/<apn>")
@login_required
def api_research_status_single(apn: str):
    """Get research status for a specific APN."""
    bill = db.get_bill(apn)
    if not bill:
        return jsonify({"error": "Property not found"}), 404
    
    return jsonify({
        "apn": apn,
        "status": bill.get("research_status") or "none",
        "report_path": bill.get("research_report_path"),
        "updated_at": bill.get("research_updated_at"),
        "has_report": bool(bill.get("research_report_path")),
    })


@app.route("/api/research/start", methods=["POST"])
@login_required
def api_research_start():
    """Start deep research for specified APNs."""
    try:
        import scanner.gemini_research_scanner as gemini_research_scanner
        gemini_research_scanner.ensure_research_columns()
        
        data = request.get_json() or {}
        apns = data.get("apns", [])

        if not apns:
            return jsonify({"status": "error", "message": "No APNs provided"})

        if not gemini_research_scanner.GOOGLE_API_KEY:
            return jsonify({"status": "error", "message": "GOOGLE_API_KEY not configured in .env"})

        # Start research without bulk marking all as pending up front
        success = gemini_research_scanner.start_research(apns)
        if success:
            return jsonify({
                "status": "ok", 
                "message": f"Research started for {len(apns)} properties"
            })
        else:
            return jsonify({"status": "error", "message": "Failed to start research"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/research/start-all", methods=["POST"])
@login_required
def api_research_start_all():
    """Start deep research for all properties that have not been fully researched."""
    try:
        import scanner.gemini_research_scanner as gemini_research_scanner
        gemini_research_scanner.ensure_research_columns()

        if not gemini_research_scanner.GOOGLE_API_KEY:
            return jsonify({"status": "error", "message": "GOOGLE_API_KEY not configured in .env"})

        # Get APNs that still need research (NULL or 'unchecked')
        apns = db.get_bills_missing_research()
        if not apns:
            return jsonify({"status": "ok", "message": "No properties need research"})

        # Start research without bulk marking all as pending up front
        success = gemini_research_scanner.start_research(apns)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Research started for {len(apns)} properties"
            })
        else:
            return jsonify({"status": "error", "message": "Failed to start research"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/research/report/<apn>")
@login_required
def api_research_report(apn: str):
    """Get the research report for an APN."""
    try:
        import scanner.gemini_research_scanner as gemini_research_scanner
        report = gemini_research_scanner.get_research_report(apn)
        
        if report:
            return jsonify({"apn": apn, "report": report})
        else:
            return jsonify({"error": "Report not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/queue")
@login_required
def api_research_queue():
    """Get the current research queue."""
    try:
        import scanner.gemini_research_scanner as gemini_research_scanner
        state = gemini_research_scanner.get_research_state()
        return jsonify({
            "queue": gemini_research_scanner.research_state["queue"][:20],  # Limit to first 20
            "queue_length": state["queue_length"],
            "current_apn": state["current_apn"],
            "is_running": state["is_running"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Owner Contact Scanner API Endpoints
# ============================================================================


@app.route("/api/contact/status")
@login_required
def api_contact_status():
    """Get current contact scanner status."""
    try:
        import scanner.contact_scanner as cs
        status = cs.get_contact_state()
        missing = db.get_bills_missing_owner_contact()
        status["pending_count"] = len(missing)
        status["scanner_available"] = True
        return jsonify(status)
    except ModuleNotFoundError:
        return jsonify({"is_running": False, "api_configured": False, "scanner_available": False})
    except Exception as e:
        return jsonify({"error": str(e), "is_running": False, "api_configured": False, "scanner_available": False})


@app.route("/api/contact/start", methods=["POST"])
@login_required
def api_contact_start():
    """Start contact scan for specific APNs."""
    try:
        import scanner.contact_scanner as cs
        data = request.get_json(force=True)
        apns = data.get("apns", [])
        if not apns:
            return jsonify({"status": "error", "message": "No APNs provided"})
        if cs.start_contact_scan(apns):
            return jsonify({"status": "ok", "message": f"Contact scan started for {len(apns)} properties"})
        else:
            return jsonify({"status": "error", "message": "Failed to start contact scan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/contact/start-all", methods=["POST"])
@login_required
def api_contact_start_all():
    """Start contact scan for all properties missing contact info."""
    try:
        import scanner.contact_scanner as cs
        apns = db.get_bills_missing_owner_contact()
        if not apns:
            return jsonify({"status": "ok", "message": "No properties need contact scanning"})
        if cs.start_contact_scan(apns):
            return jsonify({"status": "ok", "message": f"Contact scan started for {len(apns)} properties"})
        else:
            return jsonify({"status": "error", "message": "Failed to start contact scan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/contact/result/<apn>")
@login_required
def api_contact_result(apn: str):
    """Get contact scan result for a specific APN."""
    try:
        bill = db.get_bill(apn)
        if not bill:
            return jsonify({"error": "Property not found"}), 404
        return jsonify({
            "apn": apn,
            "owner_contact_status": bill.get("owner_contact_status"),
            "owner_email": bill.get("owner_email"),
            "owner_phone": bill.get("owner_phone"),
            "owner_contact_updated_at": bill.get("owner_contact_updated_at"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Property Condition Scanner API Endpoints
# ============================================================================

STREETVIEW_DIR = BASE_DIR / "streetview_images"


@app.route("/api/condition/status")
@login_required
def api_condition_status():
    """Get current condition scanner status."""
    try:
        import scanner.condition_scanner as condition_scanner
        condition_scanner.ensure_condition_columns()
        status = condition_scanner.get_condition_state()
        
        # Add DB stats
        # Condition stats from Supabase
        with_score = db.get_client().table("bills").select("condition_score").not_.is_("condition_score", "null").execute()
        scores = [r["condition_score"] for r in (with_score.data or []) if r.get("condition_score") is not None]
        total_score = sum(scores)
        count = len(scores)
        avg_score = float(f"{total_score / count:.1f}") if count else None
        status["total_scanned"] = count
        status["average_score"] = avg_score
        status["poor_condition"] = sum(1 for s in scores if s > 6.0)
        status["scanner_available"] = True
        
        return jsonify(status)
    except ModuleNotFoundError:
        return jsonify({"is_running": False, "api_configured": False, "scanner_available": False})
    except Exception as e:
        return jsonify({"error": str(e), "is_running": False, "api_configured": False, "scanner_available": False})


@app.route("/api/condition/start", methods=["POST"])
@login_required
def api_condition_start():
    """Start condition scan for specified APNs."""
    try:
        import scanner.condition_scanner as condition_scanner
        condition_scanner.ensure_condition_columns()
        
        data = request.get_json() or {}
        apns = data.get("apns", [])
        
        if not apns:
            return jsonify({"status": "error", "message": "No APNs provided"})
        
        if not condition_scanner.GOOGLE_API_KEY:
            return jsonify({"status": "error", "message": "GOOGLE_API_KEY not configured"})
        
        success = condition_scanner.start_condition_scan(apns)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Condition scan started for {len(apns)} properties"
            })
        else:
            return jsonify({"status": "error", "message": "Failed to start scan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/condition/start-all", methods=["POST"])
@login_required
def api_condition_start_all():
    """Start condition scan for all unscanned properties."""
    try:
        import scanner.condition_scanner as condition_scanner
        condition_scanner.ensure_condition_columns()
        
        if not condition_scanner.GOOGLE_API_KEY:
            return jsonify({"status": "error", "message": "GOOGLE_API_KEY not configured"})
        
        # Get all APNs without condition scores
        bills = db.get_client().table("bills").select("apn").is_("condition_score", "null").execute()
        apns = [row["apn"] for row in (bills.data or []) if row.get("apn")]
        # Filter to those with parcel/coords if needed (optional)
        
        if not apns:
            return jsonify({"status": "ok", "message": "No unscanned properties found"})
        
        success = condition_scanner.start_condition_scan(apns)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Condition scan started for {len(apns)} properties"
            })
        else:
            return jsonify({"status": "error", "message": "Failed to start scan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/condition/score/<apn>")
@login_required
def api_condition_score(apn: str):
    """Get condition score for a specific APN."""
    try:
        import scanner.condition_scanner as condition_scanner
        data = condition_scanner.get_condition_score(apn)
        
        if data:
            return jsonify({
                "apn": apn,
                "score": data["score"],
                "notes": data["notes"],
                "updated_at": data["updated_at"],
                "has_image": bool(data["image_path"]),
            })
        else:
            return jsonify({"error": "Property not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/streetview/<apn>")
@login_required
def api_streetview_image(apn: str):
    """Serve Street View image for a property."""
    safe_apn = apn.replace("/", "_").replace("\\", "_")
    image_path = STREETVIEW_DIR / f"{safe_apn}.jpg"
    
    if image_path.exists():
        return send_from_directory(STREETVIEW_DIR, f"{safe_apn}.jpg", mimetype="image/jpeg")
    else:
        return jsonify({"error": "Image not found"}), 404


# ============================================================================
# PGE Power Status Scanner API Endpoints
# ============================================================================

@app.route("/api/pge/status")
@login_required
def api_pge_status():
    """Get current PGE scanner status."""
    try:
        import scanner.pge_scanner as pge_scanner
        status = pge_scanner.get_pge_state()
        
        # Add DB stats
        status["total_power_on"] = db.get_bills_count_where(power_status="on")
        status["total_power_off"] = db.get_bills_count_where(power_status="off")
        total_bills = db.get_bills_count_where()
        status["total_unchecked"] = max(0, total_bills - status["total_power_on"] - status["total_power_off"])
        status["scanner_available"] = True
        
        return jsonify(status)
    except ModuleNotFoundError:
        return jsonify({"is_running": False, "scanner_available": False})
    except Exception as e:
        return jsonify({"error": str(e), "is_running": False, "scanner_available": False})


@app.route("/api/pge/start", methods=["POST"])
@login_required
def api_pge_start():
    """Start PGE scan for specified APNs."""
    try:
        import scanner.pge_scanner as pge_scanner
        
        data = request.get_json() or {}
        apns = data.get("apns", None)
        
        success = pge_scanner.start_pge_scan(apns)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"PGE scan started for {len(apns) if apns else 'all unchecked'} properties"
            })
        else:
            return jsonify({"status": "error", "message": "PGE scan already running"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/pge/start-all", methods=["POST"])
@login_required
def api_pge_start_all():
    """Start PGE scan for all unchecked properties."""
    try:
        import scanner.pge_scanner as pge_scanner
        
        success = pge_scanner.start_pge_scan(None)
        if success:
            return jsonify({
                "status": "ok",
                "message": "PGE scan started for all unchecked properties"
            })
        else:
            return jsonify({"status": "error", "message": "PGE scan already running"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/pge/stop", methods=["POST"])
@login_required
def api_pge_stop():
    """Stop current PGE scan."""
    try:
        import scanner.pge_scanner as pge_scanner
        success = pge_scanner.stop_pge_scan()
        if success:
            return jsonify({"status": "ok", "message": "PGE scan stopping..."})
        else:
            return jsonify({"status": "error", "message": "No scan running"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ============================================================================
# Lists API Endpoints (shared between WebUI and Android)
# ============================================================================

def ensure_lists_tables():
    """Supabase: lists/list_properties already exist; no-op."""
    db.ensure_lists_tables()


def _normalize_list_name(name: str) -> str:
    return (name or "").strip().casefold()


def _remove_legacy_favorites_lists() -> int:
    """Delete legacy user lists named 'Favorites' to avoid conflict with real favorites."""
    rows = db.get_client().table("lists").select("id, name").execute()
    legacy_ids = [
        row["id"]
        for row in (rows.data or [])
        if _normalize_list_name(row.get("name") or "") == "favorites"
    ]
    for list_id in legacy_ids:
        db.get_client().table("list_properties").delete().eq("list_id", list_id).execute()
        db.get_client().table("lists").delete().eq("id", list_id).execute()
    return len(legacy_ids)


def _build_property_summary(apn: str, row: dict[str, Any], parcel: dict[str, Any]) -> dict[str, Any]:
    try:
        x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
        y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
    except (ValueError, TypeError):
        x, y = 0, 0

    if x != 0 and y != 0:
        lat, lng = web_mercator_to_latlng(x, y)
    else:
        lat, lng = None, None

    return {
        "apn": apn,
        "address": row.get("location_of_property") or "",
        "city": row.get("city"),
        "has_vpt": row.get("has_vpt") == 1,
        "condition_score": row.get("condition_score"),
        "latitude": lat,
        "longitude": lng,
    }


def _chunked_in_query(table: str, select_fields: str, key: str, values: list[str], chunk_size: int = 200) -> list[dict]:
    if not values:
        return []
    out: list[dict] = []
    for i in range(0, len(values), chunk_size):
        chunk = values[i : i + chunk_size]
        res = db.get_client().table(table).select(select_fields).in_(key, chunk).execute()
        out.extend(res.data or [])
    return out


@app.route("/lists")
@login_required
def lists_page():
    """Lists management page."""
    ensure_lists_tables()
    return render_template("lists.html", active_nav="search")


@app.route("/api/lists", methods=["GET"])
@login_required
def api_lists_get():
    """Get all lists with property counts."""
    ensure_lists_tables()
    _remove_legacy_favorites_lists()
    return jsonify(db.get_lists())


@app.route("/api/lists", methods=["POST"])
@login_required
def api_lists_create():
    """Create a new list."""
    ensure_lists_tables()
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip() or None
    
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400
    if _normalize_list_name(name) == "favorites":
        return jsonify(
            {
                "success": False,
                "error": 'The name "Favorites" is reserved. Use the Favorites card instead.',
            }
        ), 400
    
    list_id = db.create_list(name, description)
    return jsonify({
        "success": True,
        "data": {
            "id": list_id,
            "name": name,
            "description": description,
            "property_count": 0
        }
    })


@app.route("/api/lists/<int:list_id>", methods=["GET"])
@login_required
def api_lists_get_one(list_id: int):
    """Get a single list with its properties."""
    ensure_lists_tables()
    lst = db.get_list(list_id)
    if not lst:
        return jsonify({"error": "List not found"}), 404
    
    properties = []
    for prop in db.get_list_properties(list_id):
        parcel = parse_row_json(prop.get("row_json"))
        properties.append(_build_property_summary(prop["apn"], prop, parcel))
    
    return jsonify({
        "id": lst["id"],
        "name": lst["name"],
        "description": lst.get("description"),
        "created_at": lst.get("created_at"),
        "properties": properties
    })


@app.route("/api/favorites/details", methods=["GET"])
@login_required
def api_favorites_details():
    """Get real favorites with property details (for Lists page modal)."""
    apns = [apn for apn in db.get_favorites_apns() if apn]
    if not apns:
        return jsonify(
            {
                "id": "favorites",
                "name": "Favorites",
                "description": "Global favorites",
                "properties": [],
            }
        )

    bill_rows = _chunked_in_query(
        "bills",
        "apn, location_of_property, city, has_vpt, condition_score",
        "apn",
        apns,
    )
    parcel_rows = _chunked_in_query("parcels", "APN, row_json", "APN", apns)
    bill_by_apn = {row.get("apn"): row for row in bill_rows if row.get("apn")}
    parcel_by_apn = {
        row.get("APN"): parse_row_json(row.get("row_json"))
        for row in parcel_rows
        if row.get("APN")
    }

    properties: list[dict[str, Any]] = []
    for apn in apns:
        bill = bill_by_apn.get(apn) or {}
        parcel = parcel_by_apn.get(apn) or {}
        properties.append(_build_property_summary(apn, bill, parcel))

    return jsonify(
        {
            "id": "favorites",
            "name": "Favorites",
            "description": "Global favorites",
            "properties": properties,
        }
    )


@app.route("/api/lists/<int:list_id>", methods=["DELETE"])
@login_required
def api_lists_delete(list_id: int):
    """Delete a list."""
    ensure_lists_tables()
    deleted = db.delete_list(list_id)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "List not found"}), 404


@app.route("/api/lists/<int:list_id>/add-properties", methods=["POST"])
@login_required
def api_lists_add_properties(list_id: int):
    """Add properties to a list. Supports 'all' with filters or specific APNs."""
    ensure_lists_tables()
    try:
        data = cast(dict[str, Any], request.get_json() or {})
        apns = data.get("apns", [])
        filters = cast(dict[str, Any], data.get("filters") or {})
        
        if not db.get_list(list_id):
            return jsonify({"success": False, "error": "List not found"}), 404
        
        if apns == "all" and filters:
            added = db.add_properties_to_list_from_filter(
                list_id,
                q=filters.get("q", ""),
                zip_filter=filters.get("zip", ""),
                power_filter=filters.get("power", ""),
                city_filter=(filters.get("city") or "").upper(),
                vpt_filter=filters.get("vpt", ""),
                delinquent_filter=filters.get("delinquent", ""),
                condition_filter=filters.get("condition", ""),
                outofstate_filter=filters.get("outofstate", ""),
                research_filter=filters.get("research", ""),
                owner_name_filter=filters.get("owner_name", ""),
                occupancy_filter=filters.get("occupancy_type", ""),
                ownership_filter=filters.get("ownership_type", ""),
                primary_resident_age_filter=filters.get("primary_resident_age", ""),
                deceased_count_filter=filters.get("deceased_count", ""),
                limit=0,
            )
        else:
            added = db.add_properties_to_list(list_id, list(apns) if isinstance(apns, list) else [])
        return jsonify({"success": True, "count": added})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/lists/<int:list_id>/remove-property/<apn>", methods=["DELETE"])
@login_required
def api_lists_remove_property(list_id: int, apn: str):
    """Remove a property from a list."""
    ensure_lists_tables()
    deleted = db.remove_property_from_list(list_id, apn)
    return jsonify({"success": deleted})


@app.route("/api/lists/<int:list_id>/route", methods=["GET"])
@login_required
def api_lists_route(list_id: int):
    """Generate optimized Google Maps route URL for a list."""
    ensure_lists_tables()
    waypoints = db.get_list_route_waypoints(list_id)
    
    if not waypoints:
        return jsonify({"error": "No properties with coordinates"}), 400
    
    # Google Maps supports up to 25 waypoints (including origin/destination)
    # Format: destination is last, origin is first, middle are waypoints with optimize flag
    if len(waypoints) == 1:
        url = f"https://www.google.com/maps/dir/?api=1&destination={waypoints[0]['lat']},{waypoints[0]['lng']}"
    elif len(waypoints) <= 25:
        origin = waypoints[0]
        destination = waypoints[-1]
        middle = waypoints[1:-1]
        
        waypoints_str = "|".join([f"{w['lat']},{w['lng']}" for w in middle]) if middle else ""
        
        url = f"https://www.google.com/maps/dir/?api=1"
        url += f"&origin={origin['lat']},{origin['lng']}"
        url += f"&destination={destination['lat']},{destination['lng']}"
        if waypoints_str:
            url += f"&waypoints=optimize:true|{waypoints_str}"
        url += "&travelmode=driving"
    else:
        # Split into multiple routes for 25+ properties
        # Just return first 25 for now
        origin = waypoints[0]
        destination = waypoints[24]
        middle = waypoints[1:24]
        waypoints_str = "|".join([f"{w['lat']},{w['lng']}" for w in middle])
        
        url = f"https://www.google.com/maps/dir/?api=1"
        url += f"&origin={origin['lat']},{origin['lng']}"
        url += f"&destination={destination['lat']},{destination['lng']}"
        url += f"&waypoints=optimize:true|{waypoints_str}"
        url += "&travelmode=driving"
    
    return jsonify({
        "url": url,
        "property_count": len(waypoints),
        "optimized": len(waypoints) <= 25
    })


# ============================================================================
# Scouting API Endpoints (for Android Scout App)
# ============================================================================

def ensure_scout_tables():
    """Supabase: scouting tables already exist; no-op."""
    db.ensure_scout_tables()


@app.route("/api/scout/collections", methods=["GET"])
@login_required
def api_scout_collections_list():
    """List all scouting collections."""
    ensure_scout_tables()
    return jsonify(db.get_scout_collections())


@app.route("/api/scout/collections", methods=["POST"])
@login_required
def api_scout_collections_create():
    """Create a new scouting collection."""
    ensure_scout_tables()
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip() or None
    property_apns = data.get("property_apns", []) or []
    
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400
    
    collection_id = db.create_scout_collection(name, description, property_apns)
    return jsonify({
        "success": True,
        "data": {
            "id": collection_id,
            "name": name,
            "description": description,
            "property_count": len(property_apns)
        }
    })


@app.route("/api/scout/collections/<int:collection_id>", methods=["DELETE"])
@login_required
def api_scout_collections_delete(collection_id: int):
    """Delete a scouting collection."""
    ensure_scout_tables()
    deleted = db.delete_scout_collection(collection_id)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Collection not found"}), 404


@app.route("/api/scout/collections/<int:collection_id>/properties", methods=["GET"])
@login_required
def api_scout_collection_properties(collection_id: int):
    """Get properties in a collection with coordinates."""
    ensure_scout_tables()
    properties = []
    for row in db.get_collection_properties(collection_id):
        parcel = parse_row_json(row.get("row_json"))
        try:
            x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
            y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
        except (ValueError, TypeError):
            x, y = 0, 0
        if x != 0 and y != 0:
            lat, lng = web_mercator_to_latlng(x, y)
        else:
            lat, lng = None, None
        properties.append({
            "apn": row["apn"],
            "address": row.get("location_of_property") or "",
            "latitude": lat,
            "longitude": lng,
            "has_vpt": row.get("has_vpt") == 1,
            "condition_score": row.get("condition_score"),
            "city": row.get("city"),
            "streetview_image_path": row.get("streetview_image_path")
        })
    return jsonify(properties)


@app.route("/api/scout/collections/<int:collection_id>/properties/<apn>", methods=["POST"])
@login_required
def api_scout_collection_add_property(collection_id: int, apn: str):
    """Add a property to a collection."""
    ensure_scout_tables()
    added = db.add_properties_to_collection(collection_id, [apn])
    if added:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Property already in collection"}), 400


@app.route("/api/scout/collections/<int:collection_id>/properties/<apn>", methods=["DELETE"])
@login_required
def api_scout_collection_remove_property(collection_id: int, apn: str):
    """Remove a property from a collection."""
    ensure_scout_tables()
    deleted = db.remove_property_from_collection(collection_id, apn)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Property not in collection"}), 404


@app.route("/api/scout/results", methods=["GET"])
@login_required
def api_scout_results_list():
    """Get all scout results."""
    ensure_scout_tables()
    cid = request.args.get("collection_id")
    collection_id = int(cid) if cid else None
    rows = db.get_scout_results(collection_id)
    results = [{
        "id": r["id"],
        "apn": r["apn"],
        "collection_id": r.get("collection_id"),
        "follow_up": r.get("follow_up") == 1,
        "flyered": r.get("flyered") == 1,
        "notes": r.get("notes"),
        "scouted_at": r.get("scouted_at"),
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude")
    } for r in rows]
    return jsonify(results[:100] if not collection_id else results)


@app.route("/api/scout/results", methods=["POST"])
@login_required
def api_scout_results_submit():
    """Submit a scout result."""
    ensure_scout_tables()
    data = request.get_json() or {}
    apn = data.get("apn")
    if not apn:
        return jsonify({"success": False, "error": "APN is required"}), 400
    collection_id = data.get("collection_id")
    follow_up = 1 if data.get("follow_up") else 0
    flyered = 1 if data.get("flyered") else 0
    notes = data.get("notes", "").strip() or None
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    result_id = db.upsert_scout_result(apn, collection_id, follow_up, flyered, notes, latitude, longitude)
    return jsonify({"success": True, "data": {"id": result_id}})


@app.route("/api/scout/results/stats")
@login_required
def api_scout_results_stats():
    """Get scouting statistics."""
    ensure_scout_tables()
    s = db.get_scout_stats()
    return jsonify({
        "total_visits": s["total"],
        "follow_ups": s["follow_ups"],
        "flyered": s["flyered"],
        "unique_properties": s["unique_properties"]
    })


@app.route("/api/scout/next", methods=["GET"])
@login_required
def api_scout_next():
    """
    Get the nearest unscouted property matching filters.
    
    Query params:
        lat, lng: User's current location (required)
        city: Filter by city
        q: Search query
        vpt: 1 = VPT only
        condition_min/max: Filter by condition score
        list_id: Filter properties in specific list
    """
    ensure_scout_tables()
    
    # Get user location
    try:
        user_lat = float(request.args.get("lat", 0))
        user_lng = float(request.args.get("lng", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Valid lat/lng required"}), 400
    
    if user_lat == 0 or user_lng == 0:
        return jsonify({"error": "Valid lat/lng required"}), 400
    
    # Get filter params
    city = request.args.get("city", "").strip()
    search_q = request.args.get("q", "").strip()
    vpt_only = request.args.get("vpt") == "1"
    list_id = request.args.get("list_id")
    condition_min = request.args.get("condition_min")
    condition_max = request.args.get("condition_max")
    
    # Unscouted APNs
    scout_apns = {r["apn"] for r in db.get_scout_results(None)}
    rows = db.get_bills_for_map(q=search_q, city_filter=city, vpt_filter="1" if vpt_only else "")
    rows = [r for r in rows if r.get("apn") not in scout_apns and (r.get("location_of_property") or "").strip()]
    if condition_min is not None:
        try:
            rows = [r for r in rows if (r.get("condition_score") or 0) >= float(condition_min)]
        except ValueError:
            pass
    if condition_max is not None:
        try:
            rows = [r for r in rows if (r.get("condition_score") or 0) <= float(condition_max)]
        except ValueError:
            pass
    if list_id:
        try:
            list_id_int = int(list_id)
            lp = db.get_client().table("list_properties").select("apn").eq("list_id", list_id_int).execute()
            list_apns = {row["apn"] for row in (lp.data or [])}
            rows = [r for r in rows if r.get("apn") in list_apns]
        except ValueError:
            pass
    
    if not rows:
        return jsonify({"property": None, "remaining": 0})
    
    # Find nearest property using haversine-like distance calculation
    import math
    
    def distance_km(lat1, lng1, lat2, lng2):
        """Calculate approximate distance in km using Haversine formula."""
        if lat2 is None or lng2 is None:
            return float('inf')
        R = 6371  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    nearest = None
    nearest_dist = float('inf')
    
    for row in rows:
        parcel = parse_row_json(row["row_json"])
        
        try:
            x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
            y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
        except (ValueError, TypeError):
            continue
        
        if x == 0 or y == 0:
            continue
        
        lat, lng = web_mercator_to_latlng(x, y)
        dist = distance_km(user_lat, user_lng, lat, lng)
        
        if dist < nearest_dist:
            nearest_dist = dist
            nearest = {
                "apn": row["apn"],
                "address": row.get("location_of_property"),
                "city": row.get("city"),
                "latitude": lat,
                "longitude": lng,
                "has_vpt": row.get("has_vpt") == 1,
                "condition_score": row.get("condition_score"),
                "streetview_image_path": row.get("streetview_image_path"),
                "distance_km": round(dist, 2)
            }
    
    return jsonify({
        "property": nearest,
        "remaining": len(rows) - 1 if nearest else len(rows)
    })


@app.route("/api/properties", methods=["GET"])
@login_required
def api_properties_list():
    """
    Get filtered list of properties for Android app.
    Supports same filters as WebUI.
    """
    city = request.args.get("city", "").strip()
    search_q = request.args.get("q", "").strip()
    vpt_only = request.args.get("vpt") == "1"
    scouted = request.args.get("scouted")
    list_id = request.args.get("list_id")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    
    ensure_scout_tables()
    scout_apns = {r["apn"] for r in db.get_scout_results(None)}
    
    rows, total = db.get_bills_with_parcels_filtered(q=search_q, city_filter=city, vpt_filter="1" if vpt_only else "", page=1, page_size=10000)
    rows = [r for r in rows if (r.get("location_of_property") or "").strip()]
    if scouted == "true":
        rows = [r for r in rows if r.get("apn") in scout_apns]
    elif scouted == "false":
        rows = [r for r in rows if r.get("apn") not in scout_apns]
    if list_id:
        try:
            lp = db.get_client().table("list_properties").select("apn").eq("list_id", int(list_id)).execute()
            list_apns = {row["apn"] for row in (lp.data or [])}
            rows = [r for r in rows if r.get("apn") in list_apns]
        except ValueError:
            pass
    
    total = len(rows)
    start = (page - 1) * per_page
    rows = rows[start:start + per_page]
    
    properties = []
    for row in rows:
        parcel = parse_row_json(row.get("row_json"))
        try:
            x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
            y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
        except (ValueError, TypeError):
            x, y = 0, 0
        if x != 0 and y != 0:
            lat, lng = web_mercator_to_latlng(x, y)
        else:
            lat, lng = None, None
        properties.append({
            "apn": row["apn"],
            "address": row.get("location_of_property"),
            "city": row.get("city"),
            "has_vpt": row.get("has_vpt") == 1,
            "condition_score": row.get("condition_score"),
            "latitude": lat,
            "longitude": lng,
            "is_scouted": row.get("apn") in scout_apns,
            "streetview_image_path": row.get("streetview_image_path")
        })
    
    return jsonify({
        "properties": properties,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page else 0
    })


# ---------------------------------------------------------------------------
# Outreach Pipeline API
# ---------------------------------------------------------------------------

import logging
_outreach_logger = logging.getLogger(__name__)


@app.route("/outreach")
@login_required
def outreach_page():
    return render_template(
        "outreach_new.html",
        active_nav="outreach",
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
    )


@app.route("/api/outreach/pipeline", methods=["GET"])
@login_required
def api_outreach_pipeline():
    """Get pipeline stage counts."""
    try:
        counts = db.get_outreach_pipeline_counts()
        return jsonify({"success": True, "data": counts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/list", methods=["GET"])
@login_required
def api_outreach_list():
    """Get filtered outreach list."""
    stage = request.args.get("stage")
    min_score = request.args.get("min_score", type=float)
    city = request.args.get("city")
    sort = request.args.get("sort", "outreach_score")
    order = request.args.get("order", "desc")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    try:
        rows, total = db.get_outreach_list(
            stage=stage, min_score=min_score, city=city,
            sort=sort, order=order, limit=limit, offset=offset,
        )
        return jsonify({"success": True, "data": rows, "total": total})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/score", methods=["POST"])
@login_required
def api_outreach_score():
    """Recalculate outreach scores."""
    data = request.get_json(silent=True) or {}
    apns = data.get("apns")  # None = score all

    try:
        import outreach_scorer
        started = outreach_scorer.start_scoring(apns)
        if started:
            return jsonify({"status": "ok", "message": "Scoring started"})
        else:
            return jsonify({"status": "error", "message": "Scoring already running"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/outreach/score/status", methods=["GET"])
@login_required
def api_outreach_score_status():
    """Get scoring engine status."""
    try:
        import outreach_scorer
        return jsonify(outreach_scorer.get_scorer_state())
    except Exception as e:
        return jsonify({"is_running": False, "error": str(e)})


@app.route("/api/outreach/pitch/generate", methods=["POST"])
@login_required
def api_outreach_pitch_generate():
    """Generate AI pitch drafts for given APNs."""
    data = request.get_json(silent=True) or {}
    apns = data.get("apns", [])
    if not apns:
        return jsonify({"success": False, "error": "No APNs provided"}), 400

    try:
        import pitch_generator
        started = pitch_generator.start_pitch_generation(apns)
        if started:
            return jsonify({"status": "ok", "message": f"Generating pitches for {len(apns)} properties"})
        else:
            return jsonify({"status": "error", "message": "Already running, APNs queued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/outreach/pitch/status", methods=["GET"])
@login_required
def api_outreach_pitch_status():
    """Get pitch generation status."""
    try:
        import pitch_generator
        return jsonify(pitch_generator.get_pitch_state())
    except Exception as e:
        return jsonify({"is_running": False, "error": str(e)})


@app.route("/api/outreach/<apn>", methods=["GET"])
@login_required
def api_outreach_detail(apn):
    """Get outreach detail for a property."""
    try:
        outreach_rec = db.get_outreach(apn)
        messages = db.get_outreach_messages(apn)
        return jsonify({"success": True, "outreach": outreach_rec, "messages": messages})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/stage", methods=["POST"])
@login_required
def api_outreach_update_stage(apn):
    """Update pipeline stage for a property."""
    data = request.get_json(silent=True) or {}
    stage = data.get("stage")
    if not stage:
        return jsonify({"success": False, "error": "stage required"}), 400

    try:
        notes = data.get("notes")
        db.update_outreach_stage(apn, stage, notes=notes)
        return jsonify({"success": True, "stage": stage})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/pitch", methods=["PUT"])
@login_required
def api_outreach_update_pitch(apn):
    """Update/edit the pitch draft for a property."""
    data = request.get_json(silent=True) or {}
    subject = data.get("subject")
    body = data.get("body")

    try:
        db.upsert_outreach(apn, pitch_subject=subject, pitch_draft=body)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/send", methods=["POST"])
@login_required
def api_outreach_send(apn):
    """Send outreach email for a property via OpenClaw webhook."""
    try:
        outreach_rec = db.get_outreach(apn)
        if not outreach_rec:
            return jsonify({"success": False, "error": "No outreach record found"}), 404
        if not outreach_rec.get("pitch_draft"):
            return jsonify({"success": False, "error": "No pitch draft generated"}), 400

        bill = db.get_bill(apn)
        if not bill or not bill.get("owner_email"):
            return jsonify({"success": False, "error": "No owner email available"}), 400

        # Send via OpenClaw webhook
        openclaw_url = db.get_outreach_setting("openclaw_gateway_url")
        if not openclaw_url:
            return jsonify({"success": False, "error": "OpenClaw Gateway URL not configured"}), 400

        import urllib.request

        webhook_payload = json.dumps({
            "action": "send_outreach",
            "apn": apn,
            "to_email": bill["owner_email"],
            "subject": outreach_rec.get("pitch_subject", "BARN Housing Caretaker Program"),
            "body": outreach_rec["pitch_draft"],
            "owner_name": bill.get("primary_resident_name", "Property Owner"),
            "property_address": bill.get("location_of_property", ""),
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{openclaw_url.rstrip('/')}/api/webhook/barn-outreach",
            data=webhook_payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": db.get_outreach_setting("openclaw_webhook_secret", ""),
            },
        )
        urllib.request.urlopen(req, timeout=10)

        # Log the message and update stage
        from_addr = db.get_outreach_setting("smtp_from_address", "outreach@barnhousing.org")
        db.insert_outreach_message(
            apn=apn,
            direction="outbound",
            channel="email",
            subject=outreach_rec.get("pitch_subject"),
            content=outreach_rec["pitch_draft"],
            from_address=from_addr,
            to_address=bill["owner_email"],
        )
        db.update_outreach_stage(apn, "contacted", contacted_at="now()")

        return jsonify({"success": True, "message": "Email sent"})

    except Exception as e:
        _outreach_logger.exception("Failed to send outreach for APN %s", apn)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/settings", methods=["GET"])
@login_required
def api_outreach_settings_get():
    """Get all outreach settings."""
    try:
        resp = db.get_client().table("outreach_settings").select("*").execute()
        settings = {row["key"]: row["value"] for row in (resp.data or [])}
        return jsonify({"success": True, "data": settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/settings", methods=["POST"])
@login_required
def api_outreach_settings_save():
    """Save outreach settings."""
    data = request.get_json(silent=True) or {}
    try:
        for key, value in data.items():
            db.set_outreach_setting(key, str(value))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/webhook/reply", methods=["POST"])
def api_outreach_webhook_reply():
    """Webhook endpoint for OpenClaw to report incoming replies."""
    # Verify webhook secret
    secret = request.headers.get("X-Webhook-Secret", "")
    expected = db.get_outreach_setting("openclaw_webhook_secret", "")
    if expected and secret != expected:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    apn = data.get("apn")
    if not apn:
        return jsonify({"error": "apn required"}), 400

    try:
        # Log the inbound message
        db.insert_outreach_message(
            apn=apn,
            direction="inbound",
            channel=data.get("channel", "email"),
            content=data.get("content", ""),
            subject=data.get("subject"),
            from_address=data.get("from_address"),
            to_address=data.get("to_address"),
            openclaw_message_id=data.get("openclaw_message_id"),
        )

        # Update stage
        new_stage = data.get("new_stage")
        if new_stage and new_stage in db.OUTREACH_STAGES:
            db.update_outreach_stage(apn, new_stage, last_response_at="now()")
        else:
            db.update_outreach_stage(apn, "responding", last_response_at="now()")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Barnhousing.org submission tables ──────────────────────────────────────

@app.route("/api/submissions/reports")
@login_required
def api_submissions_reports():
    """Property reports submitted via barnhousing.org."""
    try:
        limit = min(int(request.args.get("limit") or 50), 200)
        offset = int(request.args.get("offset") or 0)
        status_filter = request.args.get("status") or ""
        q = db.get_client().table("property_reports").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        data = q.range(offset, offset + limit - 1).execute()
        total_q = db.get_client().table("property_reports").select("id", count="exact")
        if status_filter:
            total_q = total_q.eq("status", status_filter)
        total = total_q.execute().count or 0
        return jsonify({"items": data.data or [], "total": total})
    except Exception as e:
        return jsonify({"error": str(e), "items": [], "total": 0}), 500


@app.route("/api/submissions/reports/<id>", methods=["PATCH"])
@login_required
def api_submissions_reports_update(id: str):
    """Update status or admin_notes on a property report."""
    try:
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in ("status", "admin_notes")}
        if not allowed:
            return jsonify({"error": "No valid fields"}), 400
        db.get_client().table("property_reports").update(allowed).eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/reports/<id>", methods=["DELETE"])
@login_required
def api_submissions_reports_delete(id: str):
    try:
        db.get_client().table("property_reports").delete().eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/volunteers")
@login_required
def api_submissions_volunteers():
    try:
        limit = min(int(request.args.get("limit") or 50), 200)
        offset = int(request.args.get("offset") or 0)
        status_filter = request.args.get("status") or ""
        q = db.get_client().table("volunteers").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        data = q.range(offset, offset + limit - 1).execute()
        total_q = db.get_client().table("volunteers").select("id", count="exact")
        if status_filter:
            total_q = total_q.eq("status", status_filter)
        total = total_q.execute().count or 0
        return jsonify({"items": data.data or [], "total": total})
    except Exception as e:
        return jsonify({"error": str(e), "items": [], "total": 0}), 500


@app.route("/api/submissions/volunteers/<id>", methods=["PATCH"])
@login_required
def api_submissions_volunteers_update(id: str):
    try:
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in ("status", "admin_notes")}
        if not allowed:
            return jsonify({"error": "No valid fields"}), 400
        db.get_client().table("volunteers").update(allowed).eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/volunteers/<id>", methods=["DELETE"])
@login_required
def api_submissions_volunteers_delete(id: str):
    try:
        db.get_client().table("volunteers").delete().eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/caretakers")
@login_required
def api_submissions_caretakers():
    try:
        limit = min(int(request.args.get("limit") or 50), 200)
        offset = int(request.args.get("offset") or 0)
        status_filter = request.args.get("status") or ""
        q = db.get_client().table("housing_applications").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        data = q.range(offset, offset + limit - 1).execute()
        total_q = db.get_client().table("housing_applications").select("id", count="exact")
        if status_filter:
            total_q = total_q.eq("status", status_filter)
        total = total_q.execute().count or 0
        return jsonify({"items": data.data or [], "total": total})
    except Exception as e:
        return jsonify({"error": str(e), "items": [], "total": 0}), 500


@app.route("/api/submissions/caretakers/<id>", methods=["PATCH"])
@login_required
def api_submissions_caretakers_update(id: str):
    try:
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in ("status", "admin_notes")}
        if not allowed:
            return jsonify({"error": "No valid fields"}), 400
        db.get_client().table("housing_applications").update(allowed).eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/caretakers/<id>", methods=["DELETE"])
@login_required
def api_submissions_caretakers_delete(id: str):
    try:
        db.get_client().table("housing_applications").delete().eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/owners")
@login_required
def api_submissions_owners():
    try:
        limit = min(int(request.args.get("limit") or 50), 200)
        offset = int(request.args.get("offset") or 0)
        status_filter = request.args.get("status") or ""
        q = db.get_client().table("owner_registrations").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        data = q.range(offset, offset + limit - 1).execute()
        total_q = db.get_client().table("owner_registrations").select("id", count="exact")
        if status_filter:
            total_q = total_q.eq("status", status_filter)
        total = total_q.execute().count or 0
        return jsonify({"items": data.data or [], "total": total})
    except Exception as e:
        return jsonify({"error": str(e), "items": [], "total": 0}), 500


@app.route("/api/submissions/owners/<id>", methods=["PATCH"])
@login_required
def api_submissions_owners_update(id: str):
    try:
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in ("status", "admin_notes")}
        if not allowed:
            return jsonify({"error": "No valid fields"}), 400
        db.get_client().table("owner_registrations").update(allowed).eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/submissions/owners/<id>", methods=["DELETE"])
@login_required
def api_submissions_owners_delete(id: str):
    try:
        db.get_client().table("owner_registrations").delete().eq("id", id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Check for --skip-check flag to bypass dependency verification
    skip_check = "--skip-check" in sys.argv
    
    if not skip_check:
        try:
            import dependency_checker
            print("Checking dependencies...")
            if not dependency_checker.verify_dependencies(exit_on_failure=False, verbose=True):
                print("\nSome dependencies are missing. The app may not work correctly.")
                print("Run './install.sh' to install all dependencies.")
                print("Or use '--skip-check' to skip this verification.\n")
        except ImportError:
            print("Note: dependency_checker.py not found, skipping startup check")
    
    bind_host = os.environ.get("VPT_WEB_HOST", "0.0.0.0")
    bind_port = int(os.environ.get("VPT_WEB_PORT", "5000"))
    app.run(host=bind_host, port=bind_port, debug=False)
