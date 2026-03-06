# Monorepo + VM Hosting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate BARN-scan and barnhousing into a single GitHub repo and serve barnhousing.org as a static Vite build from the GCloud VM, replacing Vercel.

**Architecture:** Create a new `barn` repo on GitHub with `scan/` (Flask) and `web/` (React) subdirs. Copy files from existing repos, update the systemd service to point at the new path, add an nginx server block for `barnhousing.org` serving `web/dist/`, issue a TLS cert, then update DNS to cut over from Vercel.

**Tech Stack:** Git, bash, nginx, certbot, systemd, Vite (npm), Flask.

---

## Task 1: Create new `barn` repo on GitHub and initialize locally

**Files:**
- Create: `/home/nsnfrd768/barn/barn/` (new directory)
- Create: `/home/nsnfrd768/barn/barn/README.md`
- Create: `/home/nsnfrd768/barn/barn/.gitignore`

**Step 1: Create the GitHub repo**

Go to https://github.com/new and create `Zer0phucks/barn` — public or private, no template, no README (we'll push our own).

**Step 2: Initialize local repo**

```bash
mkdir -p /home/nsnfrd768/barn/barn
cd /home/nsnfrd768/barn/barn
git init
git branch -M main
```

**Step 3: Create .gitignore**

```bash
cat > /home/nsnfrd768/barn/barn/.gitignore << 'EOF'
# Python
__pycache__/
*.pyc
*.pyo
.venv/
*.egg-info/
dist/
.env

# Node
web/node_modules/
web/dist/

# Misc
.DS_Store
*.log
EOF
```

**Step 4: Create README.md**

```bash
cat > /home/nsnfrd768/barn/barn/README.md << 'EOF'
# BARN

Bay Area Renovating Neighbors — monorepo.

## Structure

- `scan/` — BARN-scan Flask app (app.barnhousing.org)
- `web/` — barnhousing.org React SPA (barnhousing.org)

## Deploy

SSH into the VM and run:

```bash
cd /home/nsnfrd768/barn/barn
./deploy.sh
```
EOF
```

**Step 5: Initial commit**

```bash
cd /home/nsnfrd768/barn/barn
git add .
git commit -m "chore: initialize barn monorepo"
```

**Step 6: Add remote and push**

```bash
cd /home/nsnfrd768/barn/barn
git remote add origin https://github.com/Zer0phucks/barn.git
git push -u origin main
```

Expected: push succeeds, repo visible on GitHub.

---

## Task 2: Copy scan/ and web/ into the new repo

**Files:**
- Create: `/home/nsnfrd768/barn/barn/scan/` (copy of BARN-scan)
- Create: `/home/nsnfrd768/barn/barn/web/` (copy of barnhousing)

**Step 1: Copy BARN-scan → scan/**

```bash
cd /home/nsnfrd768/barn/barn
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  /home/nsnfrd768/barn/BARN-scan/ scan/
```

**Step 2: Copy barnhousing → web/**

```bash
cd /home/nsnfrd768/barn/barn
rsync -a --exclude='.git' --exclude='node_modules' --exclude='dist' \
  /home/nsnfrd768/barn/barnhousing/ web/
```

**Step 3: Verify structure**

```bash
ls /home/nsnfrd768/barn/barn/scan/webgui/
ls /home/nsnfrd768/barn/barn/web/src/
```

Expected: `scan/webgui/` contains `app.py`, `templates/` etc. `web/src/` contains React source files.

**Step 4: Commit**

```bash
cd /home/nsnfrd768/barn/barn
git add scan/ web/
git commit -m "chore: add scan and web subdirectories"
git push
```

---

## Task 3: Create deploy.sh

**Files:**
- Create: `/home/nsnfrd768/barn/barn/deploy.sh`

**Step 1: Write deploy.sh**

```bash
cat > /home/nsnfrd768/barn/barn/deploy.sh << 'EOF'
#!/bin/bash
set -e

REPO_DIR="/home/nsnfrd768/barn/barn"

echo "==> Pulling latest..."
cd "$REPO_DIR"
git pull origin main

echo "==> Building web..."
cd "$REPO_DIR/web"
npm install --silent
npm run build

echo "==> Restarting barn-scan service..."
sudo systemctl restart barn-scan

echo "==> Deploy complete."
EOF
chmod +x /home/nsnfrd768/barn/barn/deploy.sh
```

**Step 2: Verify it's executable**

```bash
ls -la /home/nsnfrd768/barn/barn/deploy.sh
```

Expected: `-rwxr-xr-x`

**Step 3: Commit**

```bash
cd /home/nsnfrd768/barn/barn
git add deploy.sh
git commit -m "feat: add deploy.sh script"
git push
```

---

## Task 4: Update systemd service to point at new scan/ path

**Files:**
- Modify: `/etc/systemd/system/barn-scan.service`

**Step 1: Read current service file**

```bash
cat /etc/systemd/system/barn-scan.service
```

Note the current `WorkingDirectory` and `ExecStart` paths — they reference `/home/nsnfrd768/barn/BARN-scan/`.

**Step 2: Update paths**

Replace `BARN-scan` → `barn/scan` in the service file. Edit with:

```bash
sudo sed -i 's|/home/nsnfrd768/barn/BARN-scan|/home/nsnfrd768/barn/barn/scan|g' \
  /etc/systemd/system/barn-scan.service
```

**Step 3: Verify the change**

```bash
cat /etc/systemd/system/barn-scan.service
```

Expected: all paths now reference `/home/nsnfrd768/barn/barn/scan/`.

**Step 4: Reload and restart**

```bash
sudo systemctl daemon-reload
sudo systemctl restart barn-scan
sleep 3
sudo systemctl status barn-scan --no-pager | head -10
```

Expected: `Active: active (running)`

**Step 5: Verify app.barnhousing.org still works**

```bash
curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:5000/login
```

Expected: `200`

**Step 6: Commit service file note**

The service file is outside the repo, so just note the change in a commit:

```bash
cd /home/nsnfrd768/barn/barn
cat >> README.md << 'EOF'

## systemd

`barn-scan.service` WorkingDirectory and ExecStart point to `/home/nsnfrd768/barn/barn/scan/`.
EOF
git add README.md
git commit -m "docs: note systemd service path"
git push
```

---

## Task 5: Build the React app

**Files:**
- Reads: `/home/nsnfrd768/barn/barn/web/package.json`
- Produces: `/home/nsnfrd768/barn/barn/web/dist/`

**Step 1: Check Node/npm are available**

```bash
node --version && npm --version
```

Expected: any recent versions (Node 18+, npm 9+). If npm isn't available, check `which bun` — the project has a `bun.lockb` so bun may be preferred.

**Step 2: Install dependencies**

```bash
cd /home/nsnfrd768/barn/barn/web
npm install
```

If npm is unavailable but bun is: `bun install` instead.

**Step 3: Build**

```bash
cd /home/nsnfrd768/barn/barn/web
npm run build
```

Expected: completes without errors. `dist/` directory created containing `index.html` and assets.

**Step 4: Verify dist exists**

```bash
ls /home/nsnfrd768/barn/barn/web/dist/
```

Expected: `index.html`, `assets/` directory.

---

## Task 6: Add nginx server block for barnhousing.org

**Files:**
- Create: `/etc/nginx/sites-available/barnhousing.org`
- Symlink: `/etc/nginx/sites-enabled/barnhousing.org`

**Step 1: Write the nginx config**

```bash
sudo tee /etc/nginx/sites-available/barnhousing.org << 'EOF'
server {
    server_name barnhousing.org www.barnhousing.org;

    root /home/nsnfrd768/barn/barn/web/dist;
    index index.html;

    # SPA routing — all paths fall back to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    listen 10.138.0.3:443 ssl;
    # Certbot will fill in ssl_certificate lines after: certbot --nginx -d barnhousing.org -d www.barnhousing.org
}

server {
    if ($host = barnhousing.org) {
        return 301 https://$host$request_uri;
    }
    if ($host = www.barnhousing.org) {
        return 301 https://barnhousing.org$request_uri;
    }

    listen 10.138.0.3:80;
    server_name barnhousing.org www.barnhousing.org;
    return 404;
}
EOF
```

**Step 2: Enable the site**

```bash
sudo ln -s /etc/nginx/sites-available/barnhousing.org /etc/nginx/sites-enabled/barnhousing.org
```

**Step 3: Test nginx config**

```bash
sudo nginx -t
```

Expected: `syntax is ok` and `test is successful`

**Step 4: Reload nginx**

```bash
sudo systemctl reload nginx
```

---

## Task 7: Issue TLS certificate for barnhousing.org

**Note:** DNS must point at the VM before certbot can issue a cert via HTTP challenge. If DNS isn't updated yet, use `--dry-run` first to verify the setup, then run for real after DNS propagates.

**Step 1: Run certbot**

```bash
sudo certbot --nginx -d barnhousing.org -d www.barnhousing.org \
  --preferred-challenges http
```

If DNS isn't pointing to the VM yet, test with `--dry-run` first:

```bash
sudo certbot --nginx -d barnhousing.org -d www.barnhousing.org --dry-run
```

Expected: cert issued, nginx config updated with `ssl_certificate` lines, auto-renewal configured.

**Step 2: Verify cert**

```bash
sudo certbot certificates | grep barnhousing.org
```

Expected: cert listed with expiry ~90 days out.

**Step 3: Test nginx still works**

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:5000/login
```

Expected: `200` (Flask still up)

---

## Task 8: Update DNS and verify

**Step 1: Update DNS A record**

In your DNS provider (wherever barnhousing.org is registered), set:

```
barnhousing.org     A    136.109.65.233
www.barnhousing.org A    136.109.65.233
```

Remove or replace any existing Vercel CNAME/A records for these hostnames.

**Step 2: Wait for propagation**

Check propagation (from the VM):

```bash
dig +short barnhousing.org A
```

Expected: `136.109.65.233`

**Step 3: Test via curl**

Once DNS resolves:

```bash
curl -s -o /dev/null -w "%{http_code}" https://barnhousing.org/
curl -s -o /dev/null -w "%{http_code}" https://www.barnhousing.org/
```

Expected: `200` for both.

**Step 4: Test SPA routing**

```bash
curl -s -o /dev/null -w "%{http_code}" https://barnhousing.org/volunteer
curl -s -o /dev/null -w "%{http_code}" https://barnhousing.org/apply
```

Expected: `200` (served by `index.html` via try_files, React Router handles client-side routing).

---

## Task 9: Test deploy.sh end-to-end

**Step 1: Make a small change to verify deploy works**

```bash
cd /home/nsnfrd768/barn/barn
echo "# deploy test" >> README.md
git add README.md
git commit -m "chore: deploy test"
git push
```

**Step 2: Run deploy.sh**

```bash
cd /home/nsnfrd768/barn/barn
./deploy.sh
```

Expected output:
```
==> Pulling latest...
==> Building web...
==> Restarting barn-scan service...
==> Deploy complete.
```

**Step 3: Verify service is still running**

```bash
sudo systemctl status barn-scan --no-pager | head -5
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login
```

Expected: `active (running)`, `200`

---

## Task 10: Clean up and archive old repos

**Step 1: Verify everything works before archiving**

- `https://app.barnhousing.org` loads BARN-scan (Flask)
- `https://barnhousing.org` loads the React SPA
- `./deploy.sh` works end-to-end

**Step 2: Update MEMORY.md**

Update `/home/nsnfrd768/.claude/projects/-home-nsnfrd768-barn/memory/MEMORY.md`:
- Change repo paths from `BARN-scan/` → `barn/scan/` and `barnhousing/` → `barn/web/`
- Add note about `deploy.sh`
- Remove Vercel reference

**Step 3: Archive old GitHub repos (optional)**

On GitHub, go to each old repo's Settings → mark as Archived, or leave them as-is. Do NOT delete until you've confirmed everything works for a few days.

**Step 4: Final commit**

```bash
cd /home/nsnfrd768/barn/barn
git log --oneline -10
```

Confirm all commits are pushed. Done.
