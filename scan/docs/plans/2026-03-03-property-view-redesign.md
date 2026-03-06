# Property View Redesign

**Date:** 2026-03-03
**Status:** Approved

## Overview

Redesign the individual property detail page (`/property/<apn>`) to replace the link viewer iframe with a street view image, add prev/next navigation, a comprehensive edit modal, outreach status, and contact info fields.

## Layout

Single-column layout replacing the current two-column (info left, link viewer right) design.

```
┌────────────────────────────────────────────────┐
│ ← Back   ← Prev   Next →   [Edit] [★] [Delete]│  topbar
├────────────────────────────────────────────────┤
│  123 Main St, Oakland           APN: 048-0001  │
│                                                │
│  ┌──────────────────────────────────────────┐  │
│  │          Street View Image               │  │  clickable → opens maps
│  └──────────────────────────────────────────┘  │
│                                                │
│  OUTREACH STATUS  [Identified ▾]              │
│                                                │
│  CONTACT INFO                                  │
│  Owner Name: John Smith                        │
│  Phone: (510) 555-1234                         │
│  Email: john@example.com                       │
│                                                │
│  PROPERTY INFORMATION                          │
│  (all existing fields)                         │
│                                                │
│  RESEARCH LINKS (moved to bottom)              │
│  [Tax Bill] [CBC Property] [Research Report]   │
└────────────────────────────────────────────────┘
```

## Changes

### 1. Remove Link Viewer System
- Remove the `viewer-wrap` right panel (iframe, viewer toolbar, viewer-empty placeholder, viewer JS)
- Remove "Open In Viewer" buttons from the links list
- Layout becomes single-column (`max-width: 860px`, centered)

### 2. Street View Image
- Display at top of page below the address heading
- **Primary source:** `/api/streetview/<apn>` (existing endpoint) if `streetview_image_path` is set in DB
- **Fallback:** Google Street View Static API — `https://maps.googleapis.com/maps/api/streetview?size=800x400&location={address_encoded}&key={GOOGLE_API_KEY}` — rendered via `<img>` tag using address from `location_of_property`
- If neither available: show a styled placeholder div with address text
- Clicking the image opens `https://www.google.com/maps/@?api=1&map_action=pano&location={address_encoded}` in a new tab
- Route passes `streetview_maps_url` and `has_streetview_image` to template

### 3. Prev/Next Navigation
- **Index view (`index.html`):** After table renders, serialize ordered APN array to `localStorage['barn_apn_list']`. Each entry: `{apn, address}`. Run on page load and after any filter/sort/page change.
- **Property page:** On load, read `barn_apn_list`, find current APN index. Show `← Prev` / `Next →` buttons in topbar with `href` set to the adjacent property URL (preserving `return_to`). Disable (grayed out) if first/last. Show adjacent property address as button title attribute.

### 4. Edit Modal
- **Trigger:** "Edit" button in topbar
- **Fields:**

  | Field | DB column | Input |
  |---|---|---|
  | Important Notes | `important_notes` | textarea |
  | Outreach Stage | `outreach_stage` | select |
  | Owner Name | `owner_name` | text |
  | Owner Phone | `owner_phone` | text |
  | Owner Email | `owner_email` | email |
  | Condition Score | `condition_score` | number 0–10, step 0.1 |
  | Condition Notes | `condition_notes` | textarea |
  | Occupancy Type | `prop_occupancy_type` | text |
  | Ownership Type | `prop_ownership_type` | text |

- **Save:** `POST /api/properties/<apn>/update` (new endpoint) — accepts JSON dict of changed fields, writes to `bills` table
- **Remove** the existing inline notes edit (absorbed into the modal)

### 5. Property Tax Bill Link Fix
- Replace stored `bill_url` with dynamically-constructed URL:
  `https://propertytax.alamedacountyca.gov/account-summary?apn={apn}`
- This is always property-specific and doesn't require DB to have a valid `bill_url`
- Applies to both the research links section and removes the dependency on `row.get("bill_url")`

### 6. Remove Google Maps Links
- Remove `maps_url` link from the research links list (street view image makes it redundant)
- Keep `maps_url` computed in route for internal use (street view fallback link)

### 7. Outreach Status Section
- Add `outreach_stage` to `property_data` dict in `property_detail` route (currently missing)
- Display as a colored badge above the Contact Info section
- Badge colors: identified=gray, qualified=blue, outreach_ready=cyan, contacted=green, responding=yellow, negotiating=orange, partnered=purple, declined=red, no_response=gray
- Editable via the edit modal

### 8. Contact Info Fields
- Add `owner_email` and `owner_phone` to `property_data` dict in `property_detail` route
- Display in a dedicated "Contact Info" section with Owner Name, Phone, Email
- All three editable via the edit modal

### 9. Research Links at Bottom
- Move research links section to bottom of page
- Remove "Open In Viewer" buttons — links open externally only
- Remove Google Maps link
- Tax Bill link uses APN-constructed URL (see §5)

## Backend Changes

### Modified route: `property_detail` in `webgui/app.py`
- Add `owner_email`, `owner_phone`, `outreach_stage` to `property_data`
- Compute `streetview_maps_url` = `https://www.google.com/maps/@?api=1&map_action=pano&location={quote_plus(location)}`
- Compute `account_summary_url` = `https://propertytax.alamedacountyca.gov/account-summary?apn={apn}` and pass as `tax_bill_url`
- Remove `maps_url` from links list (keep computed for internal use)
- Replace `bill_url` link with `tax_bill_url`

### New API endpoint: `POST /api/properties/<apn>/update`
```python
@app.route("/api/properties/<path:apn>/update", methods=["POST"])
@login_required
def api_update_property(apn):
    ALLOWED = {
        "important_notes", "outreach_stage", "owner_name", "owner_phone",
        "owner_email", "condition_score", "condition_notes",
        "prop_occupancy_type", "prop_ownership_type"
    }
    data = {k: v for k, v in request.get_json().items() if k in ALLOWED}
    db.update_bill_fields(cleaned_apn, data)
    return jsonify({"status": "ok"})
```

### New DB function: `update_bill_fields` in `db.py`
```python
def update_bill_fields(apn: str, fields: dict) -> None:
    get_client().table("bills").update(fields).eq("apn", apn).execute()
```

## Frontend Changes

### `webgui/templates/index.html`
- Add JS at bottom: after table render, collect all APN+address pairs from table rows, write to `localStorage['barn_apn_list']`
- Trigger on DOM ready and after any fetch that re-renders the table

### `webgui/templates/property.html`
- New single-column layout (remove grid, remove viewer panel)
- Add street view image block at top
- Add Outreach Status section with badge
- Add Contact Info section (owner name/phone/email)
- Move research links to bottom
- Replace inline notes edit with "Edit" button that opens modal
- Add edit modal HTML + JS
- Add prev/next nav JS (reads localStorage)
- Add `POST /api/properties/<apn>/update` save logic

## No DB Schema Changes
All required columns already exist in the `bills` table.
