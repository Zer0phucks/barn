# BARN

Bay Area Renovating Neighbors — monorepo.

## Structure

- `scan/` — BARN-scan Flask app (app.barnhousing.org)
- `web/` — barnhousing.org React SPA (barnhousing.org)

## Deploy

SSH into the VM and run:

```bash
cd /home/noob/barn
./deploy.sh
```

## systemd

User services are managed from checked-in units in `scan/service/`:

- `barn-vpt-worker.service`
- `barn-vpt-tunnel.service`

To enable push-triggered redeploys from GitHub, add these repository secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT` (optional, defaults to `22`)
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
