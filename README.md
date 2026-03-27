# BARN

Bay Area Renovating Neighbors — monorepo.

## Structure

- `scan/` — BARN-scan Flask app (app.barnhousing.org)
- `web/` — barnhousing.org React SPA (barnhousing.org)

## Deploy

SSH into the VM and run:

```bash
cd /home/nsnfrd768_gmail_com/barn
./deploy.sh
```

## systemd

Production app hosting is currently:

- `app.bayrenewal.org` on `8.229.41.24`
- system service: `barn-scan.service`
- repo path: `/home/nsnfrd768_gmail_com/barn`

Local user-scoped worker units are also checked in under `scan/service/` for non-production use:

- `barn-vpt-worker.service`
- `barn-vpt-tunnel.service`

To enable push-triggered redeploys from GitHub, add these repository secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT` (optional, defaults to `22`)
- `DEPLOY_USER`
- `DEPLOY_REPO_DIR` (optional, defaults to `/home/nsnfrd768_gmail_com/barn`)
- `DEPLOY_SSH_KEY`
