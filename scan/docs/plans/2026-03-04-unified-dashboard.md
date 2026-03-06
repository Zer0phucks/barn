# Unified Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign app.barnhousing.org into a unified four-section app (Home, Search, Scan, Outreach) with a persistent top nav and per-section side menus, merging the barnhousing.org admin data tables into the BARN-scan Flask app.

**Architecture:** Introduce a `base.html` Jinja2 layout with a top nav and a `{% block content %}` slot. Each section gets its own route + template that includes a left side menu. New Flask API routes expose barnhousing.org Supabase tables (property_reports, volunteers, housing_applications, owner_registrations) — all queried server-side using the existing service key. The Dashboard (Home) is a new page showing recent submissions.

**Tech Stack:** Flask (Jinja2), vanilla JS, existing Supabase client in `db.py` / `webgui/db_impl.py`, Leaflet.js (map, unchanged), dark theme CSS vars from outreach.html.

---

## Task 1: Create `base.html` layout template

**Files:**
- Create: `webgui/templates/base.html`

The top nav must highlight the active section. All existing pages will extend this base in later tasks. Use the dark theme CSS vars already established in `outreach.html` (`--bg: #0f0f1a`, `--surface: #1a1a2e`, etc.). The nav links are: Home (`/`), Search (`/search`), Scan (`/scan`), Outreach (`/outreach`).

**Step 1: Create `webgui/templates/base.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block title %}BARN Scanner{% endblock %}</title>
  {% block head %}{% endblock %}
  <style>
    :root {
      --bg: #0f0f1a;
      --surface: #1a1a2e;
      --surface-2: #222240;
      --border: #2a2a4a;
      --text: #e0e0f0;
      --text-muted: #8888aa;
      --primary: #3498db;
      --primary-hover: #2980b9;
      --success: #27ae60;
      --warning: #f39c12;
      --danger: #e74c3c;
      --radius: 8px;
      --topnav-h: 52px;
      --sidenav-w: 180px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
    }

    /* ── Top Nav ── */
    .topnav {
      position: fixed;
      top: 0; left: 0; right: 0;
      height: var(--topnav-h);
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      padding: 0 24px;
      gap: 0;
      z-index: 200;
    }
    .topnav-brand {
      font-weight: 700;
      font-size: 16px;
      color: var(--text);
      text-decoration: none;
      margin-right: 32px;
      letter-spacing: 0.5px;
    }
    .topnav-links {
      display: flex;
      gap: 4px;
      flex: 1;
    }
    .topnav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 500;
      padding: 6px 14px;
      border-radius: var(--radius);
      transition: background 0.15s, color 0.15s;
    }
    .topnav-links a:hover { background: var(--surface-2); color: var(--text); }
    .topnav-links a.active { background: var(--primary); color: #fff; }
    .topnav-user {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 13px;
      color: var(--text-muted);
    }
    .topnav-user a {
      color: var(--danger);
      text-decoration: none;
      font-size: 12px;
      padding: 4px 10px;
      border: 1px solid var(--danger);
      border-radius: var(--radius);
    }
    .topnav-user a:hover { background: var(--danger); color: #fff; }

    /* ── App shell ── */
    .app-shell {
      display: flex;
      margin-top: var(--topnav-h);
      min-height: calc(100vh - var(--topnav-h));
    }

    /* ── Side Nav ── */
    .sidenav {
      width: var(--sidenav-w);
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 20px 0;
      flex-shrink: 0;
      position: sticky;
      top: var(--topnav-h);
      height: calc(100vh - var(--topnav-h));
      overflow-y: auto;
    }
    .sidenav-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-muted);
      padding: 0 16px 8px;
    }
    .sidenav a {
      display: block;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13px;
      padding: 8px 16px;
      border-left: 3px solid transparent;
      transition: background 0.12s, color 0.12s;
    }
    .sidenav a:hover { background: var(--surface-2); color: var(--text); }
    .sidenav a.active {
      border-left-color: var(--primary);
      background: var(--surface-2);
      color: var(--text);
    }

    /* ── Main content ── */
    .main-content {
      flex: 1;
      padding: 28px 32px;
      overflow-x: hidden;
    }

    /* ── Cards ── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 20px;
    }
    .card h2 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      color: var(--text);
    }

    /* ── Stat boxes ── */
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .stat-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px;
      text-align: center;
    }
    .stat-box .value { font-size: 28px; font-weight: 700; color: var(--text); }
    .stat-box .label { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

    /* ── Buttons ── */
    .btn {
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      border-radius: var(--radius);
      padding: 7px 16px;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
      text-decoration: none;
    }
    .btn:hover { background: var(--border); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-success { background: var(--success); border-color: var(--success); color: #fff; }
    .btn-danger { background: var(--danger); border-color: var(--danger); color: #fff; }

    /* ── Tables ── */
    .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .data-table th {
      background: var(--surface-2);
      color: var(--text-muted);
      font-weight: 600;
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .data-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    .data-table tr:hover td { background: var(--surface-2); }
    .table-wrap { overflow-x: auto; }

    /* ── Status pills ── */
    .pill {
      display: inline-block;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      font-weight: 600;
    }
    .pill-pending  { background: rgba(243,156,18,0.2); color: var(--warning); }
    .pill-reviewing{ background: rgba(52,152,219,0.2); color: var(--primary); }
    .pill-approved { background: rgba(39,174,96,0.2);  color: var(--success); }
    .pill-rejected { background: rgba(231,76,60,0.2);  color: var(--danger); }
    .pill-active   { background: rgba(39,174,96,0.2);  color: var(--success); }
    .pill-waitlisted { background: rgba(155,89,182,0.2); color: #9b59b6; }

    /* ── Responsive ── */
    @media (max-width: 768px) {
      .sidenav { display: none; }
      .main-content { padding: 16px; }
    }
  </style>
</head>
<body>
  <nav class="topnav">
    <a class="topnav-brand" href="/">BARN</a>
    <div class="topnav-links">
      <a href="/" {% if active_nav == 'home' %}class="active"{% endif %}>Home</a>
      <a href="/search" {% if active_nav == 'search' %}class="active"{% endif %}>Search</a>
      <a href="/scan" {% if active_nav == 'scan' %}class="active"{% endif %}>Scan</a>
      <a href="/outreach" {% if active_nav == 'outreach' %}class="active"{% endif %}>Outreach</a>
    </div>
    <div class="topnav-user">
      <span>{{ session.get('user_email', '') }}</span>
      <a href="/logout">Logout</a>
    </div>
  </nav>

  <div class="app-shell">
    {% block sidenav %}{% endblock %}
    <main class="main-content">
      {% block content %}{% endblock %}
    </main>
  </div>

  {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 2: Verify file saved correctly**

```bash
wc -l /home/nsnfrd768/barn/BARN-scan/webgui/templates/base.html
```
Expected: ~200 lines.

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/base.html
git commit -m "feat: add base.html layout with top nav and side nav slots"
```

---

## Task 2: Home (Dashboard) page

**Files:**
- Create: `webgui/templates/home.html`
- Modify: `webgui/app.py` — change `index()` route to `search_page()` at `/search`, add new `home()` at `/`

The dashboard shows recent submissions from barnhousing.org (last 10 of each: property_reports, volunteers, housing_applications, owner_registrations). Data is fetched client-side via new API endpoints added in Task 5. The home page has no side menu.

**Step 1: Create `webgui/templates/home.html`**

```html
{% extends "base.html" %}
{% block title %}Home – BARN{% endblock %}

{% block content %}
<h1 style="font-size:22px; font-weight:700; margin-bottom:24px;">Dashboard</h1>

<div class="stat-grid" id="summary-stats">
  <div class="stat-box"><div class="value" id="stat-reports">–</div><div class="label">Property Reports</div></div>
  <div class="stat-box"><div class="value" id="stat-volunteers">–</div><div class="label">Volunteers</div></div>
  <div class="stat-box"><div class="value" id="stat-caretakers">–</div><div class="label">Caretaker Apps</div></div>
  <div class="stat-box"><div class="value" id="stat-owners">–</div><div class="label">Owner Registrations</div></div>
  <div class="stat-box"><div class="value" id="stat-vpt">–</div><div class="label">VPT Properties</div></div>
</div>

<div class="card">
  <h2>Recent Property Reports</h2>
  <div class="table-wrap">
    <table class="data-table">
      <thead><tr><th>Date</th><th>Address</th><th>Reporter</th><th>Status</th></tr></thead>
      <tbody id="tbl-reports"><tr><td colspan="4" style="color:var(--text-muted)">Loading…</td></tr></tbody>
    </table>
  </div>
  <div style="margin-top:10px;"><a class="btn" href="/outreach?tab=reports">View All →</a></div>
</div>

<div class="card">
  <h2>Recent Volunteer Applications</h2>
  <div class="table-wrap">
    <table class="data-table">
      <thead><tr><th>Date</th><th>Name</th><th>Email</th><th>Status</th></tr></thead>
      <tbody id="tbl-volunteers"><tr><td colspan="4" style="color:var(--text-muted)">Loading…</td></tr></tbody>
    </table>
  </div>
  <div style="margin-top:10px;"><a class="btn" href="/outreach?tab=volunteers">View All →</a></div>
</div>

<div class="card">
  <h2>Recent Caretaker Applications</h2>
  <div class="table-wrap">
    <table class="data-table">
      <thead><tr><th>Date</th><th>Name</th><th>Email</th><th>Status</th></tr></thead>
      <tbody id="tbl-caretakers"><tr><td colspan="4" style="color:var(--text-muted)">Loading…</td></tr></tbody>
    </table>
  </div>
  <div style="margin-top:10px;"><a class="btn" href="/outreach?tab=caretakers">View All →</a></div>
</div>

<div class="card">
  <h2>Recent Owner Registrations</h2>
  <div class="table-wrap">
    <table class="data-table">
      <thead><tr><th>Date</th><th>Name</th><th>Address</th><th>Status</th></tr></thead>
      <tbody id="tbl-owners"><tr><td colspan="4" style="color:var(--text-muted)">Loading…</td></tr></tbody>
    </table>
  </div>
  <div style="margin-top:10px;"><a class="btn" href="/outreach?tab=owners">View All →</a></div>
</div>
{% endblock %}

{% block scripts %}
<script>
function fmt(iso) {
  if (!iso) return '–';
  return new Date(iso).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
}
function pill(status) {
  return `<span class="pill pill-${status || 'pending'}">${status || 'pending'}</span>`;
}
async function load() {
  try {
    const [r, v, c, o, s] = await Promise.all([
      fetch('/api/submissions/reports?limit=5').then(x => x.json()),
      fetch('/api/submissions/volunteers?limit=5').then(x => x.json()),
      fetch('/api/submissions/caretakers?limit=5').then(x => x.json()),
      fetch('/api/submissions/owners?limit=5').then(x => x.json()),
      fetch('/api/scan/status').then(x => x.json()),
    ]);
    document.getElementById('stat-reports').textContent = r.total ?? '–';
    document.getElementById('stat-volunteers').textContent = v.total ?? '–';
    document.getElementById('stat-caretakers').textContent = c.total ?? '–';
    document.getElementById('stat-owners').textContent = o.total ?? '–';
    document.getElementById('stat-vpt').textContent = (s.vpt_count ?? '–').toLocaleString?.() ?? s.vpt_count ?? '–';

    document.getElementById('tbl-reports').innerHTML = (r.items || []).map(x =>
      `<tr><td>${fmt(x.created_at)}</td><td>${x.property_address || '–'}</td><td>${x.reporter_name || '–'}</td><td>${pill(x.status)}</td></tr>`
    ).join('') || '<tr><td colspan="4" style="color:var(--text-muted)">None yet</td></tr>';

    document.getElementById('tbl-volunteers').innerHTML = (v.items || []).map(x =>
      `<tr><td>${fmt(x.created_at)}</td><td>${x.name || '–'}</td><td>${x.email || '–'}</td><td>${pill(x.status)}</td></tr>`
    ).join('') || '<tr><td colspan="4" style="color:var(--text-muted)">None yet</td></tr>';

    document.getElementById('tbl-caretakers').innerHTML = (c.items || []).map(x =>
      `<tr><td>${fmt(x.created_at)}</td><td>${x.applicant_name || '–'}</td><td>${x.applicant_email || '–'}</td><td>${pill(x.status)}</td></tr>`
    ).join('') || '<tr><td colspan="4" style="color:var(--text-muted)">None yet</td></tr>';

    document.getElementById('tbl-owners').innerHTML = (o.items || []).map(x =>
      `<tr><td>${fmt(x.created_at)}</td><td>${x.owner_name || '–'}</td><td>${x.property_address || '–'}</td><td>${pill(x.status)}</td></tr>`
    ).join('') || '<tr><td colspan="4" style="color:var(--text-muted)">None yet</td></tr>';
  } catch(e) { console.error(e); }
}
load();
</script>
{% endblock %}
```

**Step 2: Add `home()` route to `app.py`**

In `webgui/app.py`, find the existing `index()` route (around line 374). Add the new home route **before** it:

```python
@app.route("/")
@login_required
def home():
    """Dashboard home page."""
    return render_template("home.html", active_nav="home")
```

Then rename the existing `/` route to `/search` and update its function name:

- Change `@app.route("/")` → `@app.route("/search")`
- Change `def index():` → `def search_page():`
- Change `return render_template("index.html", ...)` → add `active_nav="search"` to the render_template call (already done in Task 3)
- Update `url_for("index")` references in login/auth_callback to `url_for("search_page")`

Search for all `url_for("index")` occurrences:
```bash
grep -n 'url_for.*index' /home/nsnfrd768/barn/BARN-scan/webgui/app.py
```

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/home.html webgui/app.py
git commit -m "feat: add home dashboard page and /search route"
```

---

## Task 3: Migrate `index.html` → Search section with side nav

**Files:**
- Modify: `webgui/templates/index.html` — extend base.html, add side nav (List View, Map View, My Lists)

The Search section has 3 side-nav items. "List View" is the default (current index.html content). "Map View" navigates to `/map`. "My Lists" navigates to `/lists`.

**Step 1: Wrap existing index.html in base layout**

Replace the top of `index.html` (everything before the first `<style>` content and the closing `</html>`) to use Jinja2 block structure. The full file becomes:

```html
{% extends "base.html" %}
{% block title %}Search – BARN{% endblock %}

{% block head %}
<style>
  /* existing index.html styles here — keep all of them unchanged */
  /* ... paste existing <style> block content ... */
</style>
{% endblock %}

{% block sidenav %}
<nav class="sidenav">
  <div class="sidenav-label">Search</div>
  <a href="/search" class="active">List View</a>
  <a href="/map">Map View</a>
  <a href="/lists">My Lists</a>
</nav>
{% endblock %}

{% block content %}
<!-- paste existing body content here unchanged -->
{% endblock %}

{% block scripts %}
<script>
/* paste existing <script> block content unchanged */
</script>
{% endblock %}
```

**Key things to preserve exactly:**
- All filter controls, table, pagination JS
- The `{{ ... }}` Jinja template variables already in index.html

**Step 2: Test the page loads**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/search
```
Expected: 302 (redirects to login if not authenticated — that's fine, confirms route works).

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/index.html
git commit -m "feat: wrap search/list view in base layout with side nav"
```

---

## Task 4: Migrate `map.html` and `lists.html` into base layout

**Files:**
- Modify: `webgui/templates/map.html`
- Modify: `webgui/templates/lists.html`

Map view is a special case — it needs `height: calc(100vh - var(--topnav-h))` for the map, and the side nav should stay. Lists page gets the same side nav as Search.

**Step 1: Wrap map.html in base layout**

```html
{% extends "base.html" %}
{% block title %}Map View – BARN{% endblock %}

{% block head %}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
<style>
  /* existing map styles, EXCEPT the .header styles which are now replaced by base.html */
  /* Change: #map height should be calc(100vh - var(--topnav-h)) */
  #map { height: calc(100vh - var(--topnav-h)); width: 100%; }
  /* ... rest of existing map styles unchanged ... */
</style>
{% endblock %}

{% block sidenav %}
<nav class="sidenav">
  <div class="sidenav-label">Search</div>
  <a href="/search">List View</a>
  <a href="/map" class="active">Map View</a>
  <a href="/lists">My Lists</a>
</nav>
{% endblock %}

{% block content %}
<div id="map"></div>
<!-- existing map popups/controls unchanged -->
{% endblock %}

{% block scripts %}
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
<script>
/* existing map JS unchanged */
</script>
{% endblock %}
```

Note: The map's `main-content` div adds padding that fights the full-bleed map. Override it:

```css
/* In base.html or map.html head block */
body:has(#map) .main-content { padding: 0; }
```

**Step 2: Wrap lists.html in base layout** (same pattern as index.html)

```html
{% extends "base.html" %}
{% block title %}My Lists – BARN{% endblock %}
{% block sidenav %}
<nav class="sidenav">
  <div class="sidenav-label">Search</div>
  <a href="/search">List View</a>
  <a href="/map">Map View</a>
  <a href="/lists" class="active">My Lists</a>
</nav>
{% endblock %}
{% block content %}
<!-- existing lists.html body content -->
{% endblock %}
{% block scripts %}<script>/* existing lists JS */</script>{% endblock %}
```

**Step 3: Add `active_nav="search"` to the map and lists Flask routes**

In `app.py`, find the `/map` and `/lists` routes and pass `active_nav="search"` to their `render_template` calls.

```bash
grep -n '@app.route.*map\|@app.route.*lists' /home/nsnfrd768/barn/BARN-scan/webgui/app.py
```

**Step 4: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/map.html webgui/templates/lists.html webgui/app.py
git commit -m "feat: wrap map and lists in base layout with search side nav"
```

---

## Task 5: Barnhousing.org Supabase API routes

**Files:**
- Modify: `webgui/app.py` — add 8 new API routes for barnhousing.org tables

These routes query the barnhousing.org Supabase tables (property_reports, volunteers, housing_applications, owner_registrations). They use the existing `db.get_client()` which already connects to the shared Supabase project.

**Step 1: Add submission API routes to `app.py`**

Find the end of the API routes section (before the `if __name__` block or after the last route). Add:

```python
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
```

**Step 2: Quick smoke test**

```bash
cd /home/nsnfrd768/barn/BARN-scan
source .venv/bin/activate
python -c "from webgui.app import app; print('OK')"
```
Expected: `OK` (no import errors).

**Step 3: Commit**

```bash
git add webgui/app.py
git commit -m "feat: add barnhousing.org submission API routes (reports, volunteers, caretakers, owners)"
```

---

## Task 6: Scan section with side nav

**Files:**
- Create: `webgui/templates/scan.html`
- Modify: `webgui/app.py` — add `/scan` route; keep `/admin` as redirect for backward compat

The Scan section replaces the current `/admin` page. It has a side nav with 4 tabs: VPT Scanner, Research, Condition, PGE. Each tab corresponds to one of the 4 sections in the current `admin.html`. The content is JS-driven within a single page (clicking a side nav tab shows/hides the relevant card section via `data-panel` attributes).

**Step 1: Create `webgui/templates/scan.html`**

```html
{% extends "base.html" %}
{% block title %}Scan – BARN{% endblock %}

{% block head %}
<style>
  .panel { display: none; }
  .panel.active { display: block; }
  /* Reuse existing admin.html button/stat styles already in base.html */
</style>
{% endblock %}

{% block sidenav %}
<nav class="sidenav">
  <div class="sidenav-label">Scan</div>
  <a href="#vpt" class="sidenav-tab active" data-panel="panel-vpt">VPT Scanner</a>
  <a href="#research" class="sidenav-tab" data-panel="panel-research">Research</a>
  <a href="#condition" class="sidenav-tab" data-panel="panel-condition">Condition</a>
  <a href="#pge" class="sidenav-tab" data-panel="panel-pge">PGE</a>
</nav>
{% endblock %}

{% block content %}

<!-- ── VPT Scanner Panel ── -->
<div id="panel-vpt" class="panel active">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">VPT Scanner</h2>

  <div class="card">
    <h2>Scan Status <button class="btn" onclick="refreshStatus()" style="float:right;font-size:12px;">Refresh</button></h2>
    <div class="stat-grid">
      <div class="stat-box" id="status-box"><div class="value" id="status-text">-</div><div class="label">Scanner Status</div></div>
      <div class="stat-box"><div class="value" id="current-city">-</div><div class="label">Current City</div></div>
      <div class="stat-box"><div class="value" id="total-bills">-</div><div class="label">Total Records</div></div>
      <div class="stat-box"><div class="value" id="vpt-count">-</div><div class="label">VPT Properties</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Scan Controls</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:16px;">
      <select id="city-select" style="background:var(--surface-2);color:var(--text);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px;font-size:13px;min-width:180px;">
        <option value="">Select a city…</option>
      </select>
      <button class="btn btn-primary" onclick="startCityScan()" id="btn-start-city">Scan City</button>
      <button class="btn btn-success" onclick="startContinuousScan()" id="btn-continuous">Continuous Scan</button>
      <button class="btn btn-danger" onclick="stopScan()" id="btn-stop" disabled>Stop Scan</button>
    </div>
    <span id="supabase-status" style="font-size:12px;color:var(--text-muted);">Checking…</span>
  </div>

  <div class="card">
    <h2>Cities</h2>
    <div id="city-list" style="display:flex;flex-wrap:wrap;gap:8px;">Loading…</div>
  </div>

  <div class="card">
    <h2>Activity Log</h2>
    <div id="log" style="background:#1a1a2e;color:#a8e6cf;padding:16px;border-radius:8px;font-family:monospace;font-size:13px;max-height:250px;overflow-y:auto;">
      <div>[ready] Scanner panel loaded.</div>
    </div>
  </div>
</div>

<!-- ── Research Panel ── -->
<div id="panel-research" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Deep Research <span style="font-size:14px;color:var(--text-muted);font-weight:400;">(Gemini AI)</span></h2>
  <div class="card">
    <div class="stat-grid">
      <div class="stat-box" id="research-status-box"><div class="value" id="research-status-text">-</div><div class="label">Status</div></div>
      <div class="stat-box"><div class="value" id="research-current">-</div><div class="label">Current Property</div></div>
      <div class="stat-box"><div class="value" id="research-queue">0</div><div class="label">Queue</div></div>
      <div class="stat-box"><div class="value" id="research-completed">0</div><div class="label">Completed</div></div>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span id="gemini-api-status" style="font-size:12px;color:var(--text-muted);">Checking…</span>
      <span style="font-size:12px;color:var(--text-muted);">
        Completed: <strong id="research-total-completed">0</strong> | Pending: <strong id="research-total-pending">0</strong> | Failed: <strong id="research-total-failed">0</strong>
      </span>
    </div>
    <div id="research-warning-banner" style="display:none;margin-top:12px;padding:10px;border-radius:8px;background:rgba(231,76,60,0.15);color:var(--danger);font-size:13px;"></div>
    <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap;">
      <button class="btn btn-primary" onclick="researchAllFavorites()">Research All Favorites</button>
      <button class="btn btn-success" onclick="researchAllPending()">Research All Pending</button>
    </div>
  </div>
</div>

<!-- ── Condition Panel ── -->
<div id="panel-condition" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Property Condition Scanner <span style="font-size:14px;color:var(--text-muted);font-weight:400;">(Gemini Vision)</span></h2>
  <div class="card">
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">Analyzes Street View images to rate properties on a 1-10 abandonment scale.</p>
    <div class="stat-grid">
      <div class="stat-box" id="condition-status-box"><div class="value" id="condition-status-text">-</div><div class="label">Status</div></div>
      <div class="stat-box"><div class="value" id="condition-current">-</div><div class="label">Current Property</div></div>
      <div class="stat-box"><div class="value" id="condition-scanned">0</div><div class="label">Total Scanned</div></div>
      <div class="stat-box"><div class="value" id="condition-poor">0</div><div class="label">Poor Condition (7+)</div></div>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:13px;color:var(--text-muted);">Avg Score: <strong id="condition-avg">–</strong>/10</span>
      <button class="btn btn-primary" onclick="scanAllFavoritesCondition()">Scan Favorites</button>
      <button class="btn btn-success" onclick="scanAllUnscannedCondition()">Scan All Unscanned</button>
    </div>
  </div>
</div>

<!-- ── PGE Panel ── -->
<div id="panel-pge" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">PGE Power Status Scanner</h2>
  <div class="card">
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">Checks PG&amp;E outage map to determine if properties have active power service.</p>
    <div class="stat-grid">
      <div class="stat-box" id="pge-status-box"><div class="value" id="pge-status-text">-</div><div class="label">Status</div></div>
      <div class="stat-box"><div class="value" id="pge-current">-</div><div class="label">Current Address</div></div>
      <div class="stat-box"><div class="value" id="pge-checked">0</div><div class="label">Checked</div></div>
      <div class="stat-box"><div class="value" id="pge-unchecked">0</div><div class="label">Unchecked</div></div>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:13px;color:var(--text-muted);">
        Power On: <strong id="pge-power-on" style="color:var(--success);">0</strong> | Power Off: <strong id="pge-power-off" style="color:var(--danger);">0</strong>
      </span>
      <button class="btn btn-success" onclick="startPgeScanAll()" id="btn-pge-all">Scan All Unchecked</button>
      <button class="btn btn-primary" onclick="startPgeScanFavorites()" id="btn-pge-favorites">Scan Favorites</button>
      <button class="btn btn-danger" onclick="stopPgeScan()" id="btn-pge-stop" disabled>Stop</button>
    </div>
  </div>
</div>

{% endblock %}

{% block scripts %}
<script>
// ── Tab routing via hash ──────────────────────────────
const panelMap = { vpt: 'panel-vpt', research: 'panel-research', condition: 'panel-condition', pge: 'panel-pge' };

function activateTab(hash) {
  const key = (hash || '').replace('#', '') || 'vpt';
  const panelId = panelMap[key] || 'panel-vpt';
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidenav-tab').forEach(a => {
    a.classList.toggle('active', a.dataset.panel === panelId);
  });
  const el = document.getElementById(panelId);
  if (el) el.classList.add('active');
}

document.querySelectorAll('.sidenav-tab').forEach(a => {
  a.addEventListener('click', e => { e.preventDefault(); history.pushState(null, '', a.getAttribute('href')); activateTab(a.getAttribute('href')); });
});
activateTab(window.location.hash);

// ── All scanner JS from admin.html, unchanged ────────
let pollInterval = null;
let lastResearchWarning = '';

function log(message, type = 'info') {
  const logEl = document.getElementById('log');
  if (!logEl) return;
  const entry = document.createElement('div');
  const time = new Date().toLocaleTimeString();
  entry.textContent = `[${time}] ${message}`;
  entry.style.color = type === 'error' ? '#ff7675' : type === 'warn' ? '#f9ca24' : '#a8e6cf';
  logEl.insertBefore(entry, logEl.firstChild);
}

/* ── Paste ALL JS functions from existing admin.html here unchanged ──
   refreshStatus, startCityScan, startContinuousScan, stopScan,
   refreshResearchStatus, researchAllFavorites, researchAllPending,
   refreshConditionStatus, scanAllFavoritesCondition, scanAllUnscannedCondition,
   refreshPgeStatus, startPgeScanAll, startPgeScanFavorites, stopPgeScan
   ── End paste ── */

// Start polling
refreshStatus();
pollInterval = setInterval(refreshStatus, 5000);
refreshResearchStatus();
setInterval(refreshResearchStatus, 5000);
refreshConditionStatus();
setInterval(refreshConditionStatus, 5000);
refreshPgeStatus();
setInterval(refreshPgeStatus, 5000);
</script>
{% endblock %}
```

**Step 2: Add `/scan` route and keep `/admin` as redirect in `app.py`**

```python
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
```

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/scan.html webgui/app.py
git commit -m "feat: add scan section with side nav tabs (VPT, Research, Condition, PGE)"
```

---

## Task 7: Outreach section with side nav + barnhousing.org tabs

**Files:**
- Create: `webgui/templates/outreach_new.html` (then rename, replacing current outreach.html)
- Modify: `webgui/app.py` — update `/outreach` route

The Outreach section has 5 side-nav tabs: Reports, Owners, Volunteers, Caretakers, Documents. The first 4 fetch from the API routes added in Task 5. "Documents" shows the static legal document templates from barnhousing.org's LegalDocumentsTable — rendered as an HTML table with copy/view actions. The existing outreach pipeline content (funnel, property list) moves to a 6th tab called "Pipeline" added at the top of the side nav, becoming the default.

Side nav order:
1. Pipeline (default — current outreach.html content)
2. Reports
3. Owners
4. Volunteers
5. Caretakers
6. Documents

**Step 1: Create `webgui/templates/outreach_new.html`**

```html
{% extends "base.html" %}
{% block title %}Outreach – BARN{% endblock %}

{% block head %}
<style>
  /* Paste all existing outreach.html CSS here unchanged, EXCEPT .header styles */
  .panel { display: none; }
  .panel.active { display: block; }

  /* Submission table action buttons */
  .action-cell { display: flex; gap: 6px; flex-wrap: wrap; }
  .status-select {
    background: var(--surface-2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 4px 8px;
    font-size: 12px;
    cursor: pointer;
  }
</style>
{% endblock %}

{% block sidenav %}
<nav class="sidenav">
  <div class="sidenav-label">Outreach</div>
  <a href="#pipeline" class="sidenav-tab active" data-panel="panel-pipeline">Pipeline</a>
  <a href="#reports" class="sidenav-tab" data-panel="panel-reports">Reports</a>
  <a href="#owners" class="sidenav-tab" data-panel="panel-owners">Owners</a>
  <a href="#volunteers" class="sidenav-tab" data-panel="panel-volunteers">Volunteers</a>
  <a href="#caretakers" class="sidenav-tab" data-panel="panel-caretakers">Caretakers</a>
  <a href="#documents" class="sidenav-tab" data-panel="panel-documents">Documents</a>
</nav>
{% endblock %}

{% block content %}

<!-- ── Pipeline Panel (existing outreach content) ── -->
<div id="panel-pipeline" class="panel active">
  <!-- Paste ALL existing outreach.html body content here unchanged -->
</div>

<!-- ── Reports Panel ── -->
<div id="panel-reports" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Property Reports</h2>
  <div class="card">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
      <select id="reports-status-filter" class="status-select" onchange="loadReports()">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="reviewing">Reviewing</option>
        <option value="approved">Approved</option>
        <option value="rejected">Rejected</option>
      </select>
      <span style="font-size:13px;color:var(--text-muted);">Total: <strong id="reports-total">–</strong></span>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Date</th><th>Address</th><th>Reporter</th><th>Issue</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="tbl-reports-full"><tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Owners Panel ── -->
<div id="panel-owners" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Owner Registrations</h2>
  <div class="card">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
      <select id="owners-status-filter" class="status-select" onchange="loadOwners()">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="reviewing">Reviewing</option>
        <option value="approved">Approved</option>
      </select>
      <span style="font-size:13px;color:var(--text-muted);">Total: <strong id="owners-total">–</strong></span>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Date</th><th>Owner Name</th><th>Property Address</th><th>Contact</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="tbl-owners-full"><tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Volunteers Panel ── -->
<div id="panel-volunteers" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Volunteer Applications</h2>
  <div class="card">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
      <select id="volunteers-status-filter" class="status-select" onchange="loadVolunteers()">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="active">Active</option>
      </select>
      <span style="font-size:13px;color:var(--text-muted);">Total: <strong id="volunteers-total">–</strong></span>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Date</th><th>Name</th><th>Email</th><th>Phone</th><th>Skills</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="tbl-volunteers-full"><tr><td colspan="7" style="color:var(--text-muted)">Loading…</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Caretakers Panel ── -->
<div id="panel-caretakers" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Caretaker Applications</h2>
  <div class="card">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
      <select id="caretakers-status-filter" class="status-select" onchange="loadCaretakers()">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="reviewing">Reviewing</option>
        <option value="approved">Approved</option>
        <option value="waitlisted">Waitlisted</option>
      </select>
      <span style="font-size:13px;color:var(--text-muted);">Total: <strong id="caretakers-total">–</strong></span>
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Date</th><th>Name</th><th>Email</th><th>Family Size</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="tbl-caretakers-full"><tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Documents Panel ── -->
<div id="panel-documents" class="panel">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;">Legal Document Templates</h2>
  <div class="card">
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">Legal templates for the BARN program. Click to view or copy.</p>
    <table class="data-table">
      <thead><tr><th>Document</th><th>Category</th><th>Description</th><th>Actions</th></tr></thead>
      <tbody id="tbl-documents">
        <!-- Rows injected by JS from DOCUMENTS constant below -->
      </tbody>
    </table>
  </div>
  <div id="doc-viewer" style="display:none;" class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 id="doc-viewer-title" style="font-size:16px;"></h2>
      <button class="btn" onclick="closeDoc()">✕ Close</button>
    </div>
    <pre id="doc-viewer-body" style="white-space:pre-wrap;font-size:13px;color:var(--text);background:var(--surface-2);padding:16px;border-radius:var(--radius);max-height:500px;overflow-y:auto;"></pre>
    <div style="margin-top:12px;display:flex;gap:8px;">
      <button class="btn btn-primary" onclick="copyDoc()">Copy to Clipboard</button>
    </div>
  </div>
</div>

{% endblock %}

{% block scripts %}
<script>
// ── Tab routing ──
const panelIds = ['panel-pipeline','panel-reports','panel-owners','panel-volunteers','panel-caretakers','panel-documents'];
const hashMap = { pipeline:'panel-pipeline', reports:'panel-reports', owners:'panel-owners', volunteers:'panel-volunteers', caretakers:'panel-caretakers', documents:'panel-documents' };

function activateTab(hash) {
  const key = (hash || '').replace('#','') || 'pipeline';
  const panelId = hashMap[key] || 'panel-pipeline';
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidenav-tab').forEach(a => {
    a.classList.toggle('active', a.dataset.panel === panelId);
  });
  const el = document.getElementById(panelId);
  if (el) el.classList.add('active');
  // Load data for the activated panel
  if (panelId === 'panel-reports') loadReports();
  if (panelId === 'panel-owners') loadOwners();
  if (panelId === 'panel-volunteers') loadVolunteers();
  if (panelId === 'panel-caretakers') loadCaretakers();
  if (panelId === 'panel-documents') renderDocuments();
}

document.querySelectorAll('.sidenav-tab').forEach(a => {
  a.addEventListener('click', e => { e.preventDefault(); history.pushState(null,'',a.getAttribute('href')); activateTab(a.getAttribute('href')); });
});
window.addEventListener('popstate', () => activateTab(window.location.hash));
activateTab(window.location.hash);

// ── Helpers ──
function fmt(iso) {
  if (!iso) return '–';
  return new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
}
function pill(status) {
  return `<span class="pill pill-${status||'pending'}">${status||'pending'}</span>`;
}
async function patchStatus(endpoint, id, status) {
  await fetch(`/api/submissions/${endpoint}/${id}`, {
    method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({status})
  });
}
async function deleteRow(endpoint, id, reloadFn) {
  if (!confirm('Delete this record?')) return;
  await fetch(`/api/submissions/${endpoint}/${id}`, {method:'DELETE'});
  reloadFn();
}

// ── Reports ──
async function loadReports() {
  const status = document.getElementById('reports-status-filter')?.value || '';
  const tbody = document.getElementById('tbl-reports-full');
  tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr>';
  const data = await fetch(`/api/submissions/reports?limit=100&status=${encodeURIComponent(status)}`).then(r=>r.json());
  document.getElementById('reports-total').textContent = data.total ?? 0;
  tbody.innerHTML = (data.items||[]).map(x => `
    <tr>
      <td>${fmt(x.created_at)}</td>
      <td>${x.property_address||'–'}</td>
      <td>${x.reporter_name||'–'}<br><span style="color:var(--text-muted);font-size:11px;">${x.reporter_email||''}</span></td>
      <td style="max-width:200px;">${(x.issue_description||'').slice(0,80)}${x.issue_description?.length>80?'…':''}</td>
      <td>${pill(x.status)}</td>
      <td class="action-cell">
        <select class="status-select" onchange="patchStatus('reports','${x.id}',this.value).then(loadReports)">
          ${['pending','reviewing','approved','rejected'].map(s=>`<option value="${s}" ${x.status===s?'selected':''}>${s}</option>`).join('')}
        </select>
        <button class="btn btn-danger" onclick="deleteRow('reports','${x.id}',loadReports)" style="padding:4px 8px;">✕</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="color:var(--text-muted)">No records</td></tr>';
}

// ── Owners ──
async function loadOwners() {
  const status = document.getElementById('owners-status-filter')?.value || '';
  const tbody = document.getElementById('tbl-owners-full');
  tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr>';
  const data = await fetch(`/api/submissions/owners?limit=100&status=${encodeURIComponent(status)}`).then(r=>r.json());
  document.getElementById('owners-total').textContent = data.total ?? 0;
  tbody.innerHTML = (data.items||[]).map(x => `
    <tr>
      <td>${fmt(x.created_at)}</td>
      <td>${x.owner_name||'–'}</td>
      <td>${x.property_address||'–'}</td>
      <td>${x.contact_email||x.contact_phone||'–'}</td>
      <td>${pill(x.status)}</td>
      <td class="action-cell">
        <select class="status-select" onchange="patchStatus('owners','${x.id}',this.value).then(loadOwners)">
          ${['pending','reviewing','approved'].map(s=>`<option value="${s}" ${x.status===s?'selected':''}>${s}</option>`).join('')}
        </select>
        <button class="btn btn-danger" onclick="deleteRow('owners','${x.id}',loadOwners)" style="padding:4px 8px;">✕</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="color:var(--text-muted)">No records</td></tr>';
}

// ── Volunteers ──
async function loadVolunteers() {
  const status = document.getElementById('volunteers-status-filter')?.value || '';
  const tbody = document.getElementById('tbl-volunteers-full');
  tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-muted)">Loading…</td></tr>';
  const data = await fetch(`/api/submissions/volunteers?limit=100&status=${encodeURIComponent(status)}`).then(r=>r.json());
  document.getElementById('volunteers-total').textContent = data.total ?? 0;
  tbody.innerHTML = (data.items||[]).map(x => `
    <tr>
      <td>${fmt(x.created_at)}</td>
      <td>${x.name||'–'}</td>
      <td>${x.email||'–'}</td>
      <td>${x.phone||'–'}</td>
      <td style="max-width:150px;">${(x.skills||[]).join(', ')||'–'}</td>
      <td>${pill(x.status)}</td>
      <td class="action-cell">
        <select class="status-select" onchange="patchStatus('volunteers','${x.id}',this.value).then(loadVolunteers)">
          ${['pending','approved','active'].map(s=>`<option value="${s}" ${x.status===s?'selected':''}>${s}</option>`).join('')}
        </select>
        <button class="btn btn-danger" onclick="deleteRow('volunteers','${x.id}',loadVolunteers)" style="padding:4px 8px;">✕</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="7" style="color:var(--text-muted)">No records</td></tr>';
}

// ── Caretakers ──
async function loadCaretakers() {
  const status = document.getElementById('caretakers-status-filter')?.value || '';
  const tbody = document.getElementById('tbl-caretakers-full');
  tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">Loading…</td></tr>';
  const data = await fetch(`/api/submissions/caretakers?limit=100&status=${encodeURIComponent(status)}`).then(r=>r.json());
  document.getElementById('caretakers-total').textContent = data.total ?? 0;
  tbody.innerHTML = (data.items||[]).map(x => `
    <tr>
      <td>${fmt(x.created_at)}</td>
      <td>${x.applicant_name||'–'}</td>
      <td>${x.applicant_email||'–'}</td>
      <td>${x.family_size||'–'}</td>
      <td>${pill(x.status)}</td>
      <td class="action-cell">
        <select class="status-select" onchange="patchStatus('caretakers','${x.id}',this.value).then(loadCaretakers)">
          ${['pending','reviewing','approved','waitlisted'].map(s=>`<option value="${s}" ${x.status===s?'selected':''}>${s}</option>`).join('')}
        </select>
        <button class="btn btn-danger" onclick="deleteRow('caretakers','${x.id}',loadCaretakers)" style="padding:4px 8px;">✕</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="color:var(--text-muted)">No records</td></tr>';
}

// ── Documents ──
const DOCUMENTS = [
  { id:'inspection-authorization', title:'Authorization to Enter and Inspect Property', category:'Owner', description:'Owner permission for BARN to enter and inspect property for 30 days.' },
  { id:'caretaker-agreement', title:'Caretaker Occupancy Agreement', category:'Caretaker', description:'Formal agreement between BARN, property owner, and caretaker.' },
  { id:'renovation-agreement', title:'Property Renovation Agreement', category:'Owner', description:'Terms for BARN to perform renovation work on the property.' },
  { id:'outreach-letter', title:'Initial Owner Outreach Letter', category:'Outreach', description:'Template letter for first contact with property owners.' },
  { id:'followup-letter', title:'Follow-Up Owner Letter', category:'Outreach', description:'Second outreach letter for non-responding owners.' },
];

// Full document content map — paste content from LegalDocumentsTable.tsx DOCUMENTS array
const DOC_CONTENT = {
  'inspection-authorization': `AUTHORIZATION TO ENTER AND INSPECT PROPERTY\n\n[Full content from LegalDocumentsTable.tsx]`,
  // Add remaining docs
};

function renderDocuments() {
  document.getElementById('tbl-documents').innerHTML = DOCUMENTS.map(d => `
    <tr>
      <td><strong>${d.title}</strong></td>
      <td><span class="pill" style="background:var(--surface-2);color:var(--text-muted);">${d.category}</span></td>
      <td style="color:var(--text-muted);font-size:12px;">${d.description}</td>
      <td><button class="btn btn-primary" onclick="viewDoc('${d.id}','${d.title.replace(/'/g,"\\'")}')" style="padding:4px 10px;font-size:12px;">View</button></td>
    </tr>
  `).join('');
}

let currentDocContent = '';
function viewDoc(id, title) {
  currentDocContent = DOC_CONTENT[id] || '(Content not yet loaded)';
  document.getElementById('doc-viewer-title').textContent = title;
  document.getElementById('doc-viewer-body').textContent = currentDocContent;
  document.getElementById('doc-viewer').style.display = 'block';
  document.getElementById('doc-viewer').scrollIntoView({behavior:'smooth'});
}
function closeDoc() { document.getElementById('doc-viewer').style.display = 'none'; }
function copyDoc() {
  navigator.clipboard.writeText(currentDocContent).then(() => alert('Copied to clipboard'));
}

/* ── Paste ALL existing outreach.html JS here unchanged for the Pipeline panel ── */
</script>
{% endblock %}
```

**Step 2: Update `/outreach` route in `app.py`**

```python
@app.route("/outreach")
@login_required
def outreach_page():
    """Outreach section."""
    return render_template("outreach_new.html", active_nav="outreach")
```

**Step 3: Copy full content from current outreach.html into outreach_new.html**

Copy the entire existing `outreach.html` body content and all its JS into the `panel-pipeline` div and the scripts block respectively.

**Step 4: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/outreach_new.html webgui/app.py
git commit -m "feat: add outreach section with pipeline + submission tabs (reports, owners, volunteers, caretakers, documents)"
```

---

## Task 8: Migrate `property.html` into base layout

**Files:**
- Modify: `webgui/templates/property.html`

Property detail page should use the top nav (no side nav). The back button already links to `/`.

**Step 1: Wrap property.html in base layout**

```html
{% extends "base.html" %}
{% block title %}{{ bill.location_of_property or bill.apn }} – BARN{% endblock %}
{% block head %}
<style>/* existing property.html styles */</style>
{% endblock %}
{% block content %}
<!-- existing body content, remove .header div -->
{% endblock %}
{% block scripts %}<script>/* existing JS */</script>{% endblock %}
```

Update back link from `href="/"` to `href="/search"`.

**Step 2: Update the property route `active_nav`**

```bash
grep -n '@app.route.*property\|def property' /home/nsnfrd768/barn/BARN-scan/webgui/app.py | head -5
```

Add `active_nav="search"` to the property route's `render_template` call.

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add webgui/templates/property.html webgui/app.py
git commit -m "feat: wrap property detail in base layout"
```

---

## Task 9: Update barnhousing.org admin to redirect

**Files:**
- Modify: `barnhousing/src/App.tsx` — change admin routes

The `/admin` and `/admin/dashboard` routes on barnhousing.org should redirect to `https://app.barnhousing.org`.

**Step 1: Find admin routes in App.tsx**

```bash
grep -n 'admin\|Admin' /home/nsnfrd768/barn/barnhousing/src/App.tsx
```

**Step 2: Replace AdminLogin and AdminDashboard routes**

Find the routes that render `AdminLogin` and `AdminDashboard` and replace them with:

```tsx
<Route path="/admin" element={<Navigate to="https://app.barnhousing.org" replace />} />
<Route path="/admin/dashboard" element={<Navigate to="https://app.barnhousing.org" replace />} />
```

Note: React Router's `<Navigate>` only works for in-app paths. For external redirects, use a component:

```tsx
const ExternalRedirect = ({ to }: { to: string }) => {
  useEffect(() => { window.location.href = to; }, [to]);
  return null;
};
// Then:
<Route path="/admin" element={<ExternalRedirect to="https://app.barnhousing.org" />} />
<Route path="/admin/dashboard" element={<ExternalRedirect to="https://app.barnhousing.org" />} />
```

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/barnhousing
git add src/App.tsx
git commit -m "feat: redirect /admin to app.barnhousing.org"
```

---

## Task 10: Final wiring, smoke test, deploy

**Step 1: Restart barn-scan service**

```bash
sudo systemctl restart barn-scan
sudo journalctl -u barn-scan -f --no-pager -n 30
```
Expected: Flask starts on port 5000, no import errors.

**Step 2: Smoke test all routes**

Open a browser or use curl with session cookies to verify:
- `https://app.barnhousing.org/` → Home dashboard loads
- `https://app.barnhousing.org/search` → List view with top nav + side nav
- `https://app.barnhousing.org/map` → Map view
- `https://app.barnhousing.org/lists` → My Lists
- `https://app.barnhousing.org/scan` → Scan section, all 4 tabs work
- `https://app.barnhousing.org/outreach` → Pipeline tab (existing content), other 5 tabs load data
- `https://app.barnhousing.org/admin` → Redirects to `/scan`

**Step 3: Deploy barnhousing React changes**

```bash
cd /home/nsnfrd768/barn/barnhousing
git push origin main
```
Vercel auto-deploys on push.

**Step 4: Final commit**

```bash
cd /home/nsnfrd768/barn/BARN-scan
git add -A
git commit -m "chore: unified dashboard complete"
```

---

## Quick Reference: Field names in barnhousing.org tables

| Table | Key display fields |
|---|---|
| `property_reports` | `reporter_name`, `reporter_email`, `property_address`, `issue_description`, `status`, `created_at` |
| `volunteers` | `name`, `email`, `phone`, `skills` (array), `status`, `created_at` |
| `housing_applications` | `applicant_name`, `applicant_email`, `applicant_phone`, `family_size`, `status`, `created_at` |
| `owner_registrations` | `owner_name`, `property_address`, `contact_email`, `contact_phone`, `status`, `created_at` |

> **Note:** Verify actual column names against Supabase schema if any field returns `undefined` — column names in the React types file (`barnhousing/src/integrations/supabase/types.ts`) are the source of truth.
