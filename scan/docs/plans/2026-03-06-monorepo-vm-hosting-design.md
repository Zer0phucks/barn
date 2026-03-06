# Monorepo + VM Hosting Migration Design

**Date:** 2026-03-06

## Goal

Consolidate BARN-scan and barnhousing into a single GitHub repo (`Zer0phucks/barn`) and host barnhousing.org on the GCloud VM instead of Vercel.

## Repo Structure

New repo at `~/barn/barn/` (or cloned to `/home/nsnfrd768/barn/barn/`):

```
barn/
├── scan/          ← BARN-scan Flask app
├── web/           ← barnhousing React SPA
├── deploy.sh      ← pull + build + restart script
└── README.md
```

Fresh git history — no history merge from old repos.

## Deploy Script (`deploy.sh`)

```bash
#!/bin/bash
set -e
cd /home/nsnfrd768/barn/barn
git pull origin main
cd web && npm install && npm run build
cd ..
sudo systemctl restart barn-scan
echo "Deploy complete."
```

## nginx

New server block for `barnhousing.org` + `www.barnhousing.org`:
- Serves `/home/nsnfrd768/barn/barn/web/dist/` as static files
- `try_files $uri /index.html` for SPA routing
- TLS via certbot (`certbot --nginx -d barnhousing.org -d www.barnhousing.org`)
- Bind to `10.138.0.3:443` (same pattern as existing app.barnhousing.org block)
- Existing `app.barnhousing.org` block unchanged

## systemd

Update `barn-scan.service`:
- `WorkingDirectory=/home/nsnfrd768/barn/barn/scan`
- `ExecStart` path updated accordingly

## DNS

Point `barnhousing.org` A record to `136.109.65.233`. Done after nginx + cert are confirmed working (can test via `/etc/hosts` override first).

## What doesn't change

- Supabase project, tables, auth
- `app.barnhousing.org` domain and nginx config
- Certbot auto-renewal timer
