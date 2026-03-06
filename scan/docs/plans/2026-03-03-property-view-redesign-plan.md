# Property View Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign `/property/<apn>` to remove the iframe link viewer, add a street view image, prev/next navigation via localStorage, a comprehensive edit modal, outreach status display, and contact info fields.

**Architecture:** Single-column layout replacing two-column. Backend adds 3 new fields to `property_data`, 1 new API endpoint, 1 new DB function. Frontend changes touch `index.html` (localStorage write) and fully rewrite `property.html`. No DB schema changes needed.

**Tech Stack:** Flask/Jinja2, vanilla JS, Supabase via `db.py`, no build step.

---

## Task 1: Add `update_bill_fields` to db layer

**Files:**
- Modify: `db.py` (after `update_property_notes` function, around line 1409)
- Modify: `webgui/db_impl.py` (mirror the same function, same location pattern)

This is the lowest-level change with no dependencies. All higher-level endpoint/template changes depend on it.

**Step 1: Add the function to `db.py`**

Find `update_property_notes` at the bottom of `db.py` (line ~1407) and add the new function immediately after:

```python
def update_bill_fields(apn: str, fields: dict) -> None:
    """Update arbitrary allowed fields on a bills row."""
    if not fields:
        return
    get_client().table("bills").update(fields).eq("apn", apn).execute()
```

**Step 2: Add the same function to `webgui/db_impl.py`**

Find the mirror of `update_property_notes` in `webgui/db_impl.py` and add `update_bill_fields` immediately after it with identical code.

**Step 3: Verify with a quick smoke test**

```bash
cd /home/nsnfrd768/barn/BARN-scan
source .venv/bin/activate
python -c "import db; print(hasattr(db, 'update_bill_fields'))"
# Expected: True
```

**Step 4: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add db.py webgui/db_impl.py
git commit -m "feat: add update_bill_fields helper to db layer"
```

---

## Task 2: Add `POST /api/properties/<apn>/update` endpoint

**Files:**
- Modify: `webgui/app.py` — add after `api_update_property_notes` (line ~1071)

**Step 1: Add the endpoint**

Immediately after the `api_update_property_notes` function (after line 1070), insert:

```python
@app.route("/api/properties/<path:apn>/update", methods=["POST"])
@login_required
def api_update_property(apn: str):
    """Update editable fields for a property."""
    ALLOWED_FIELDS = {
        "important_notes", "outreach_stage", "owner_name", "owner_phone",
        "owner_email", "condition_score", "condition_notes",
        "prop_occupancy_type", "prop_ownership_type",
    }
    cleaned_apn = _clean_apn(apn)
    if not cleaned_apn:
        return jsonify({"status": "error", "message": "APN is required"}), 400

    payload = request.get_json() or {}
    fields = {k: v for k, v in payload.items() if k in ALLOWED_FIELDS}
    if not fields:
        return jsonify({"status": "error", "message": "No valid fields provided"}), 400

    # Coerce condition_score to float if present
    if "condition_score" in fields:
        try:
            val = fields["condition_score"]
            fields["condition_score"] = float(val) if val not in (None, "", "null") else None
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "condition_score must be a number"}), 400

    try:
        db.update_bill_fields(cleaned_apn, fields)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
```

**Step 2: Restart the service and smoke-test with curl**

```bash
sudo systemctl restart barn-scan
sleep 2

# Replace <APN> with a real APN from your DB, e.g. 048-1234-001
# Replace <COOKIE> with a valid session cookie from your browser dev tools
curl -s -X POST \
  http://localhost:5000/api/properties/048-0001-001/update \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<COOKIE>" \
  -d '{"important_notes": "test note"}'
# Expected: {"status": "ok"}
```

**Step 3: Commit**

```bash
git add webgui/app.py
git commit -m "feat: add POST /api/properties/<apn>/update endpoint"
```

---

## Task 3: Update `property_detail` route to expose new fields

**Files:**
- Modify: `webgui/app.py` — `property_detail` function (lines ~532–612)

**Step 1: Add missing fields to `property_data` dict**

In the `property_detail` function, find the `property_data = {` block (line ~578). Add the following keys to the dict (after `"is_favorite": ...`):

```python
        "owner_email": row.get("owner_email") or "",
        "owner_phone": row.get("owner_phone") or "",
        "outreach_stage": row.get("outreach_stage") or "identified",
        "prop_occupancy_type": row.get("prop_occupancy_type") or "",
        "prop_ownership_type": row.get("prop_ownership_type") or "",
        "primary_resident_name": row.get("primary_resident_name") or "",
        "primary_resident_age": row.get("primary_resident_age") or "",
        "deceased_count": row.get("deceased_count"),
        "prop_last_sale_date": row.get("prop_last_sale_date") or "",
```

**Step 2: Add computed URL fields**

In the same function, before the `return_to = ...` line (line ~577), add:

```python
    from urllib.parse import quote_plus as _qp
    streetview_maps_url = (
        f"https://www.google.com/maps/@?api=1&map_action=pano&location={_qp(location)}"
        if location else ""
    )
    tax_bill_url = f"https://propertytax.alamedacountyca.gov/account-summary?apn={apn}"
```

Note: `quote_plus` is already imported at the top of `app.py` as `quote_plus`. Use that instead of the local import. Check the import at the top of `app.py` with: `grep "quote_plus" webgui/app.py | head -3`.

Then add these two to `property_data`:

```python
        "streetview_maps_url": streetview_maps_url,
        "tax_bill_url": tax_bill_url,
```

**Step 3: Fix the links list — remove Google Maps, fix tax bill link**

In the `property_detail` function, find the `links: list[dict[str, str]] = []` block (lines ~552–575). Replace the entire links-building block with:

```python
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
    # Google Maps link intentionally removed (street view image replaces it)
```

**Step 4: Verify no Python errors**

```bash
cd /home/nsnfrd768/barn/BARN-scan
source .venv/bin/activate
python -c "import webgui.app; print('OK')"
# Expected: OK
```

**Step 5: Commit**

```bash
git add webgui/app.py
git commit -m "feat: expose owner_email, owner_phone, outreach_stage, tax_bill_url in property detail route"
```

---

## Task 4: Add localStorage APN list to `index.html`

**Files:**
- Modify: `webgui/templates/index.html` — add a `<script>` block after `</tbody>` (line ~734)

**Step 1: Inject APN list after the table body**

Find the `{% endfor %}` line followed by `</tbody>` (around line 733). Immediately after `</tbody>`, insert:

```html
<script>
  // Store ordered APN list for prev/next navigation in property detail view
  (function () {
    const list = [
      {% for r in rows %}
      { apn: {{ r.apn | tojson }}, address: {{ (r.location_of_property or r.apn) | tojson }} }{% if not loop.last %},{% endif %}
      {% endfor %}
    ];
    try { localStorage.setItem("barn_apn_list", JSON.stringify(list)); } catch (e) {}
  })();
</script>
```

This runs on every page load of the list view, updating the stored list to match the current filter/sort/page state.

**Step 2: Verify in browser**

1. Load the property list page
2. Open DevTools → Application → Local Storage
3. Confirm `barn_apn_list` key exists and contains an array of `{apn, address}` objects

**Step 3: Commit**

```bash
git add webgui/templates/index.html
git commit -m "feat: serialize ordered APN list to localStorage for property prev/next nav"
```

---

## Task 5: Rewrite `property.html`

**Files:**
- Modify: `webgui/templates/property.html` — full rewrite

This is the largest task. Replace the entire file with the new design. Key structural changes:
- Single-column layout (max-width 860px, centered)
- Street view image at top (clickable → opens Google Maps pano)
- Outreach status badge section
- Contact info section (owner name/phone/email)
- Edit modal covering all editable fields
- Notes removed from inline edit — now in modal
- Research links at bottom (external-only, no viewer buttons)
- Prev/next nav in topbar from localStorage

**Step 1: Replace the full file**

Replace `/home/nsnfrd768/barn/BARN-scan/webgui/templates/property.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ property.display_name }} - BARN</title>
  <style>
    :root {
      --bg: #f7f9fc;
      --panel: #ffffff;
      --border: #d8e0eb;
      --text: #1f2937;
      --muted: #667085;
      --primary: #1f6feb;
      --primary-hover: #1959bc;
      --success: #1f8f4d;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }

    /* Topbar */
    .topbar {
      display: flex; align-items: center; justify-content: space-between; gap: 10px;
      padding: 10px 16px; border-bottom: 1px solid var(--border);
      background: var(--panel); position: sticky; top: 0; z-index: 20; flex-wrap: wrap;
    }
    .topbar-left, .topbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

    /* Buttons */
    .btn, .link-btn {
      border: 1px solid var(--border); background: #fff; color: var(--text);
      border-radius: 6px; padding: 7px 12px; font-size: 13px; cursor: pointer;
      text-decoration: none; display: inline-flex; align-items: center; gap: 5px;
    }
    .btn:hover, .link-btn:hover { background: #f2f6fb; }
    .btn.primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    .btn.primary:hover { background: var(--primary-hover); }
    .btn.favorite.active { background: #fef3c7; border-color: #f59e0b; color: #92400e; }
    .btn.danger { color: var(--danger); border-color: #f5c6c2; }
    .btn.danger:hover { background: #fff1f0; border-color: var(--danger); }
    .btn:disabled { opacity: 0.5; cursor: default; pointer-events: none; }

    /* Main content */
    .content {
      max-width: 860px; margin: 0 auto; padding: 16px;
    }

    .property-heading { margin-bottom: 14px; }
    .property-heading h1 { margin: 0 0 4px; font-size: 22px; line-height: 1.2; }
    .subtitle { color: var(--muted); font-size: 14px; }

    /* Street view */
    .streetview-block {
      margin-bottom: 16px; border-radius: 10px; overflow: hidden;
      border: 1px solid var(--border); background: #f0f4fa;
      min-height: 180px; display: flex; align-items: center; justify-content: center;
    }
    .streetview-block a { display: block; width: 100%; }
    .streetview-block img {
      display: block; width: 100%; max-height: 380px; object-fit: cover;
      transition: opacity 0.15s;
    }
    .streetview-block img:hover { opacity: 0.88; }
    .streetview-placeholder {
      padding: 32px; text-align: center; color: var(--muted); font-size: 14px;
    }
    .streetview-placeholder a { color: var(--primary); }

    /* Panel / section */
    .panel {
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 10px; padding: 16px; margin-bottom: 14px;
    }
    .panel h2 { margin: 0 0 12px; font-size: 16px; }

    /* Outreach badge */
    .outreach-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .outreach-badge {
      display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px;
      font-weight: 600; text-transform: capitalize; letter-spacing: 0.02em;
    }
    .stage-identified    { background: #f3f4f6; color: #374151; }
    .stage-qualified     { background: #dbeafe; color: #1e40af; }
    .stage-outreach_ready{ background: #cffafe; color: #164e63; }
    .stage-contacted     { background: #d1fae5; color: #065f46; }
    .stage-responding    { background: #fef9c3; color: #713f12; }
    .stage-negotiating   { background: #fed7aa; color: #7c2d12; }
    .stage-partnered     { background: #ede9fe; color: #4c1d95; }
    .stage-declined      { background: #fee2e2; color: #7f1d1d; }
    .stage-no_response   { background: #f3f4f6; color: #6b7280; }

    /* Key-value grid */
    .kv-grid { display: grid; grid-template-columns: 160px 1fr; gap: 7px 10px; font-size: 14px; }
    .kv-grid dt { color: var(--muted); }
    .kv-grid dd { margin: 0; word-break: break-word; }
    .score-good { color: var(--success); font-weight: bold; }
    .score-bad  { color: var(--danger);  font-weight: bold; }

    /* Research links */
    .links-list { display: flex; flex-direction: column; gap: 7px; }
    .link-item {
      display: flex; align-items: center; justify-content: space-between;
      border: 1px solid #ebeff5; border-radius: 8px; padding: 8px 12px;
      background: #fafcff; font-size: 14px;
    }
    .link-item .label { font-weight: 600; }
    .link-item a {
      color: var(--primary); text-decoration: none; font-size: 13px;
      border: 1px solid var(--primary); border-radius: 5px; padding: 4px 10px;
    }
    .link-item a:hover { background: #edf4ff; }

    /* Dialogs */
    .dialog-overlay {
      display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.45);
      z-index: 100; align-items: center; justify-content: center;
    }
    .dialog-overlay.open { display: flex; }
    .dialog-box {
      background: #fff; border-radius: 10px; padding: 24px 28px;
      max-width: 520px; width: 94%; box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      max-height: 90vh; overflow-y: auto;
    }
    .dialog-box h3 { margin: 0 0 14px; font-size: 18px; }
    .dialog-box p  { margin: 0 0 18px; color: var(--muted); font-size: 14px; line-height: 1.5; }
    .dialog-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }

    /* Edit form */
    .edit-form { display: flex; flex-direction: column; gap: 12px; }
    .form-group { display: flex; flex-direction: column; gap: 4px; }
    .form-group label { font-size: 13px; font-weight: 600; color: var(--muted); }
    .form-group input, .form-group textarea, .form-group select {
      width: 100%; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px;
      font-family: inherit; font-size: 14px; color: var(--text); background: #fff;
    }
    .form-group textarea { resize: vertical; min-height: 70px; }
    .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
      outline: 2px solid var(--primary); outline-offset: 1px;
    }
    .form-section-title {
      font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--muted); border-top: 1px solid #edf1f7; padding-top: 10px; margin-top: 4px;
    }

    @media (max-width: 600px) {
      .kv-grid { grid-template-columns: 1fr; gap: 4px; }
      .kv-grid dt { margin-top: 8px; font-weight: 600; color: var(--text); }
      .kv-grid dd { margin-bottom: 8px; border-bottom: 1px solid #edf1f7; padding-bottom: 8px; }
      .topbar { flex-direction: column; align-items: stretch; }
      .topbar-left, .topbar-right { justify-content: center; }
      .content { padding: 8px; }
    }
  </style>
</head>
<body>

<header class="topbar">
  <div class="topbar-left">
    <a class="link-btn" href="{{ return_to }}">← Back</a>
    <a class="link-btn" id="prev-btn" href="#" style="display:none;">← Prev</a>
    <a class="link-btn" id="next-btn" href="#" style="display:none;">Next →</a>
  </div>
  <div class="topbar-right">
    <button id="edit-btn" class="btn primary">Edit</button>
    <button id="favorite-btn" class="btn favorite {% if property.is_favorite %}active{% endif %}">
      {% if property.is_favorite %}★ Favorited{% else %}☆ Favorite{% endif %}
    </button>
    <button id="delete-btn" class="btn danger">🗑 Delete</button>
    <a class="link-btn" href="/logout">Logout</a>
  </div>
</header>

<main class="content">

  <!-- Heading -->
  <div class="property-heading">
    <h1>{{ property.display_name }}</h1>
    <div class="subtitle">
      APN: {{ property.apn }}{% if property.city %} &bull; {{ property.city }}{% endif %}
    </div>
  </div>

  <!-- Street View -->
  <div class="streetview-block" id="streetview-block">
    {% if property.streetview_image_path %}
    <a href="{{ property.streetview_maps_url }}" target="_blank" rel="noopener" title="Open in Google Street View">
      <img
        src="/api/streetview/{{ property.apn }}"
        alt="Street view of {{ property.display_name }}"
        id="streetview-img"
        onerror="handleStreetviewError()"
      />
    </a>
    {% else %}
    <div class="streetview-placeholder" id="streetview-placeholder">
      <div style="font-size: 28px; margin-bottom: 8px;">🏠</div>
      <div>No street view image captured yet.</div>
      {% if property.streetview_maps_url %}
      <div style="margin-top: 8px;">
        <a href="{{ property.streetview_maps_url }}" target="_blank" rel="noopener">View on Google Maps →</a>
      </div>
      {% endif %}
    </div>
    {% endif %}
  </div>

  <!-- Outreach Status -->
  <div class="panel">
    <h2>Outreach Status</h2>
    <div class="outreach-row">
      <span class="outreach-badge stage-{{ property.outreach_stage }}" id="outreach-badge">
        {{ property.outreach_stage | replace("_", " ") | title }}
      </span>
      <span style="font-size: 13px; color: var(--muted);">Edit to change stage</span>
    </div>
  </div>

  <!-- Contact Info -->
  <div class="panel">
    <h2>Contact Info</h2>
    <dl class="kv-grid">
      <dt>Owner Name</dt>
      <dd id="disp-owner_name">{{ property.owner_name or "-" }}</dd>
      <dt>Phone</dt>
      <dd id="disp-owner_phone">{{ property.owner_phone or "-" }}</dd>
      <dt>Email</dt>
      <dd id="disp-owner_email">{{ property.owner_email or "-" }}</dd>
    </dl>
  </div>

  <!-- Property Information -->
  <div class="panel">
    <h2>Property Information</h2>
    <dl class="kv-grid">
      <dt>Location</dt>
      <dd>{{ property.location_of_property or "-" }}</dd>
      <dt>APN</dt>
      <dd>{{ property.apn }}</dd>
      <dt>Parcel #</dt>
      <dd>{{ property.parcel_number or "-" }}</dd>
      <dt>Tracer #</dt>
      <dd>{{ property.tracer_number or "-" }}</dd>
      <dt>Tax Year</dt>
      <dd>{{ property.tax_year or "-" }}</dd>
      <dt>Last Payment</dt>
      <dd>{{ property.last_payment or "-" }}</dd>
      <dt>Delinquent</dt>
      <dd>{{ property.delinquent }}</dd>
      <dt>Power</dt>
      <dd>{{ property.power_status }}</dd>
      <dt>VPT</dt>
      <dd>{{ property.has_vpt }}</dd>
      <dt>Condition Score</dt>
      <dd id="disp-condition_score">
        {% if property.condition_score is not none %}
        <span class="{% if property.condition_score > 6.0 %}score-bad{% else %}score-good{% endif %}">
          {{ "%.1f"|format(property.condition_score) }}
        </span>
        {% else %}-{% endif %}
      </dd>
      <dt>Condition Notes</dt>
      <dd id="disp-condition_notes" style="white-space: pre-wrap;">{{ property.condition_notes or "-" }}</dd>
      <dt>Occupancy Type</dt>
      <dd id="disp-prop_occupancy_type">{{ property.prop_occupancy_type or "-" }}</dd>
      <dt>Ownership Type</dt>
      <dd id="disp-prop_ownership_type">{{ property.prop_ownership_type or "-" }}</dd>
      <dt>Last Sale Date</dt>
      <dd>{{ property.prop_last_sale_date or "-" }}</dd>
      <dt>Primary Resident</dt>
      <dd>{{ property.primary_resident_name or "-" }}</dd>
      <dt>Primary Resident Age</dt>
      <dd>{{ property.primary_resident_age or "-" }}</dd>
      <dt>Deceased Count</dt>
      <dd>{% if property.deceased_count is not none %}{{ property.deceased_count }}{% else %}-{% endif %}</dd>
      <dt>Research Status</dt>
      <dd>{{ property.research_status }}</dd>
      <dt>Mailing Address</dt>
      <dd>{{ property.mailing_address or "-" }}</dd>
      <dt>Situs Address</dt>
      <dd>{{ property.situs_address or "-" }}</dd>
      <dt>Situs City</dt>
      <dd>{{ property.situs_city or "-" }}</dd>
      <dt>Situs Zip</dt>
      <dd>{{ property.situs_zip or "-" }}</dd>
      <dt>Important Notes</dt>
      <dd id="disp-important_notes" style="white-space: pre-wrap;">{{ property.important_notes or "-" }}</dd>
    </dl>
  </div>

  <!-- Research Links -->
  <div class="panel">
    <h2>Research Links</h2>
    <div class="links-list">
      {% if links %}
      {% for link in links %}
      <div class="link-item">
        <div class="label">{{ link.label }}</div>
        <a href="{{ link.url }}" target="_blank" rel="noopener">Open &rarr;</a>
      </div>
      {% endfor %}
      {% else %}
      <div style="color: var(--muted); font-size: 14px;">No research links available yet.</div>
      {% endif %}
    </div>
  </div>

</main>

<!-- Edit Dialog -->
<div class="dialog-overlay" id="edit-dialog-overlay">
  <div class="dialog-box">
    <h3>Edit Property</h3>
    <div class="edit-form">

      <div class="form-section-title">Outreach</div>
      <div class="form-group">
        <label for="edit-outreach_stage">Outreach Stage</label>
        <select id="edit-outreach_stage">
          <option value="identified">Identified</option>
          <option value="qualified">Qualified</option>
          <option value="outreach_ready">Outreach Ready</option>
          <option value="contacted">Contacted</option>
          <option value="responding">Responding</option>
          <option value="negotiating">Negotiating</option>
          <option value="partnered">Partnered</option>
          <option value="declined">Declined</option>
          <option value="no_response">No Response</option>
        </select>
      </div>

      <div class="form-section-title">Contact Info</div>
      <div class="form-group">
        <label for="edit-owner_name">Owner Name</label>
        <input type="text" id="edit-owner_name" />
      </div>
      <div class="form-group">
        <label for="edit-owner_phone">Phone</label>
        <input type="text" id="edit-owner_phone" />
      </div>
      <div class="form-group">
        <label for="edit-owner_email">Email</label>
        <input type="email" id="edit-owner_email" />
      </div>

      <div class="form-section-title">Property Details</div>
      <div class="form-group">
        <label for="edit-prop_occupancy_type">Occupancy Type</label>
        <input type="text" id="edit-prop_occupancy_type" />
      </div>
      <div class="form-group">
        <label for="edit-prop_ownership_type">Ownership Type</label>
        <input type="text" id="edit-prop_ownership_type" />
      </div>
      <div class="form-group">
        <label for="edit-condition_score">Condition Score (0–10)</label>
        <input type="number" id="edit-condition_score" min="0" max="10" step="0.1" />
      </div>
      <div class="form-group">
        <label for="edit-condition_notes">Condition Notes</label>
        <textarea id="edit-condition_notes"></textarea>
      </div>

      <div class="form-section-title">Notes</div>
      <div class="form-group">
        <label for="edit-important_notes">Important Notes</label>
        <textarea id="edit-important_notes"></textarea>
      </div>

    </div>
    <div class="dialog-actions">
      <button id="edit-cancel-btn" class="btn">Cancel</button>
      <button id="edit-save-btn" class="btn primary">Save</button>
    </div>
  </div>
</div>

<!-- Delete Dialog -->
<div class="dialog-overlay" id="delete-dialog-overlay">
  <div class="dialog-box">
    <h3 style="color: var(--danger);">Delete Property</h3>
    <p>Permanently remove <strong>{{ property.location_of_property or property.apn }}</strong>
      (APN: {{ property.apn }}) from the database? This cannot be undone.</p>
    <div class="dialog-actions">
      <button id="delete-cancel-btn" class="btn">Cancel</button>
      <button id="delete-confirm-btn" class="btn danger">Delete</button>
    </div>
  </div>
</div>

<script>
  const apn = {{ property.apn | tojson }};
  const returnTo = {{ return_to | tojson }};
  let isFavorite = {{ property.is_favorite | tojson | default('false') }};

  // ── Prev / Next navigation from localStorage ──────────────────────────────
  (function () {
    try {
      const list = JSON.parse(localStorage.getItem("barn_apn_list") || "[]");
      const idx = list.findIndex(item => item.apn === apn);
      if (idx === -1 || list.length < 2) return;

      const buildUrl = (item) =>
        `/property/${encodeURIComponent(item.apn)}?return_to=${encodeURIComponent(returnTo)}`;

      const prevBtn = document.getElementById("prev-btn");
      const nextBtn = document.getElementById("next-btn");

      if (idx > 0) {
        const prev = list[idx - 1];
        prevBtn.href = buildUrl(prev);
        prevBtn.title = prev.address;
        prevBtn.style.display = "inline-flex";
      }
      if (idx < list.length - 1) {
        const next = list[idx + 1];
        nextBtn.href = buildUrl(next);
        nextBtn.title = next.address;
        nextBtn.style.display = "inline-flex";
      }
    } catch (e) {}
  })();

  // ── Street view error fallback ────────────────────────────────────────────
  function handleStreetviewError() {
    const img = document.getElementById("streetview-img");
    const block = document.getElementById("streetview-block");
    const mapsUrl = {{ property.streetview_maps_url | tojson }};
    if (img) img.style.display = "none";
    block.innerHTML = `<div class="streetview-placeholder">
      <div style="font-size:28px;margin-bottom:8px;">🏠</div>
      <div>Street view image not available.</div>
      ${mapsUrl ? `<div style="margin-top:8px;"><a href="${mapsUrl}" target="_blank" rel="noopener">View on Google Maps →</a></div>` : ""}
    </div>`;
  }

  // ── Favorite ──────────────────────────────────────────────────────────────
  const favoriteBtn = document.getElementById("favorite-btn");
  function renderFavoriteBtn() {
    favoriteBtn.classList.toggle("active", isFavorite);
    favoriteBtn.textContent = isFavorite ? "★ Favorited" : "☆ Favorite";
  }
  favoriteBtn.addEventListener("click", async () => {
    try {
      const res = await fetch(`/api/favorites/${encodeURIComponent(apn)}/toggle`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || data.status !== "ok") throw new Error(data.error || "Failed");
      isFavorite = Boolean(data.favorited);
      renderFavoriteBtn();
    } catch (err) { alert("Error: " + err.message); }
  });

  // ── Delete ────────────────────────────────────────────────────────────────
  const deleteOverlay = document.getElementById("delete-dialog-overlay");
  document.getElementById("delete-btn").addEventListener("click", () => deleteOverlay.classList.add("open"));
  document.getElementById("delete-cancel-btn").addEventListener("click", () => deleteOverlay.classList.remove("open"));
  deleteOverlay.addEventListener("click", e => { if (e.target === deleteOverlay) deleteOverlay.classList.remove("open"); });
  document.getElementById("delete-confirm-btn").addEventListener("click", async function () {
    this.disabled = true; this.textContent = "Deleting…";
    try {
      const res = await fetch(`/api/property/${encodeURIComponent(apn)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok || data.status !== "ok") throw new Error(data.message || "Delete failed");
      window.location.href = returnTo;
    } catch (err) {
      alert("Error: " + err.message);
      this.disabled = false; this.textContent = "Delete";
      deleteOverlay.classList.remove("open");
    }
  });

  // ── Edit Modal ────────────────────────────────────────────────────────────
  const EDITABLE_FIELDS = [
    "outreach_stage", "owner_name", "owner_phone", "owner_email",
    "prop_occupancy_type", "prop_ownership_type",
    "condition_score", "condition_notes", "important_notes"
  ];

  // Current display values (pre-populate from server render)
  const CURRENT = {
    outreach_stage: {{ property.outreach_stage | tojson }},
    owner_name:     {{ property.owner_name | tojson }},
    owner_phone:    {{ property.owner_phone | tojson }},
    owner_email:    {{ property.owner_email | tojson }},
    prop_occupancy_type: {{ property.prop_occupancy_type | tojson }},
    prop_ownership_type: {{ property.prop_ownership_type | tojson }},
    condition_score: {{ property.condition_score | tojson if property.condition_score is not none else 'null' }},
    condition_notes: {{ property.condition_notes | tojson }},
    important_notes: {{ property.important_notes | tojson }},
  };

  const editOverlay = document.getElementById("edit-dialog-overlay");
  const editSaveBtn = document.getElementById("edit-save-btn");
  const editCancelBtn = document.getElementById("edit-cancel-btn");

  function openEditModal() {
    // Populate all fields from CURRENT values
    EDITABLE_FIELDS.forEach(field => {
      const el = document.getElementById("edit-" + field);
      if (!el) return;
      el.value = CURRENT[field] != null ? CURRENT[field] : "";
    });
    editOverlay.classList.add("open");
  }

  function closeEditModal() { editOverlay.classList.remove("open"); }

  document.getElementById("edit-btn").addEventListener("click", openEditModal);
  editCancelBtn.addEventListener("click", closeEditModal);
  editOverlay.addEventListener("click", e => { if (e.target === editOverlay) closeEditModal(); });

  editSaveBtn.addEventListener("click", async () => {
    // Collect all field values
    const payload = {};
    EDITABLE_FIELDS.forEach(field => {
      const el = document.getElementById("edit-" + field);
      if (!el) return;
      payload[field] = el.value.trim() === "" ? null : el.value.trim();
    });
    // condition_score: send as number or null
    if (payload.condition_score !== null) {
      const n = parseFloat(payload.condition_score);
      payload.condition_score = isNaN(n) ? null : n;
    }

    editSaveBtn.disabled = true;
    editSaveBtn.textContent = "Saving…";
    try {
      const res = await fetch(`/api/properties/${encodeURIComponent(apn)}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.status !== "ok") throw new Error(data.message || "Save failed");

      // Update in-memory state and display elements
      EDITABLE_FIELDS.forEach(field => {
        CURRENT[field] = payload[field];
        const dispEl = document.getElementById("disp-" + field);
        if (dispEl) dispEl.textContent = payload[field] || "-";
      });

      // Update outreach badge specially
      const stage = payload.outreach_stage || "identified";
      const badge = document.getElementById("outreach-badge");
      if (badge) {
        badge.className = "outreach-badge stage-" + stage;
        badge.textContent = stage.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      }

      closeEditModal();
    } catch (err) {
      alert("Error saving: " + err.message);
    } finally {
      editSaveBtn.disabled = false;
      editSaveBtn.textContent = "Save";
    }
  });
</script>

</body>
</html>
```

**Step 2: Restart service and verify in browser**

```bash
sudo systemctl restart barn-scan
```

Open a property page in the browser and verify:
- [ ] Topbar shows Back, Prev, Next (Prev/Next only after visiting the list page)
- [ ] Street view image renders (or placeholder if no image captured)
- [ ] Clicking street view image opens Google Maps in new tab
- [ ] Outreach Status badge renders with correct color
- [ ] Contact Info section shows owner name/phone/email
- [ ] Edit button opens modal with all fields pre-populated
- [ ] Save updates the displayed values without page reload
- [ ] Research Links are at the bottom with external-only links
- [ ] Tax Bill link uses `account-summary?apn=...` URL
- [ ] Delete button works

**Step 3: Verify prev/next nav**

1. Go to the property list (index page)
2. Click into any property
3. Confirm Prev/Next buttons appear with correct adjacent addresses in tooltips
4. Confirm navigation works

**Step 4: Commit**

```bash
git add webgui/templates/property.html
git commit -m "feat: redesign property detail view - street view image, edit modal, prev/next nav, outreach status, contact info"
```

---

## Task 6: Final verification

**Step 1: Full smoke-test checklist**

```
[ ] Property list page loads, localStorage barn_apn_list populated
[ ] Property detail: street view image shown (or placeholder)
[ ] Property detail: clicking image opens Google Maps street view
[ ] Property detail: Prev/Next buttons navigate correctly
[ ] Property detail: Outreach status badge correct color per stage
[ ] Property detail: Contact info (name/phone/email) displayed
[ ] Property detail: Edit modal opens, all fields pre-populated
[ ] Property detail: Saving edit updates display instantly
[ ] Property detail: Tax Bill link is APN-specific (account-summary?apn=...)
[ ] Property detail: Research Links at bottom, no "Open in Viewer" buttons
[ ] Property detail: Favorite toggle still works
[ ] Property detail: Delete still works
[ ] /api/properties/<apn>/update rejects non-allowed fields
```

**Step 2: Check service logs for errors**

```bash
journalctl -u barn-scan --since "5 minutes ago" -n 50
# Expected: No Python tracebacks
```

**Step 3: Commit design doc**

```bash
git add docs/
git commit -m "docs: add property view redesign design doc and plan"
```
