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

## systemd

`barn-scan.service` WorkingDirectory and ExecStart point to `/home/nsnfrd768/barn/barn/scan/`.

