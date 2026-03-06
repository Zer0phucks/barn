# OpenClaw Setup Guide for BARN-scan

This guide covers installing and configuring [OpenClaw](https://github.com/openclaw/openclaw) as the AI-powered email gateway for BARN-scan's outreach pipeline. OpenClaw handles outbound email delivery (SMTP), inbound reply detection (IMAP), and AI-driven conversational follow-up using the `barn-outreach` skill.

---

## Prerequisites

- **Node.js 18+** (LTS recommended)
- **BARN-scan** running and accessible (local or deployed)
- An **SMTP-capable email account** for sending outreach emails
- An **IMAP-capable email account** for receiving replies (can be the same account)
- A Supabase-backed BARN-scan instance with the outreach pipeline tables configured

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BARN-scan (Python/Flask)                 │
│                                                                 │
│  Outreach Pipeline:                                             │
│    1. Score properties (outreach_scorer.py)                     │
│    2. Generate pitch emails (pitch_generator.py + Gemini)       │
│    3. Send via OpenClaw webhook ──────────────────┐             │
│    4. Receive reply webhooks from OpenClaw ◄──────┼──────┐      │
│                                                   │      │      │
│  Webhook Endpoints:                               │      │      │
│    POST /api/outreach/<apn>/send  ────────────────┘      │      │
│    POST /api/outreach/webhook/reply  ◄───────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                         │                    ▲
                         │ HTTP POST          │ HTTP POST
                         │ (send request)     │ (reply notification)
                         ▼                    │
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw Gateway (Node.js)                  │
│                                                                 │
│  Webhook Receiver:                                              │
│    POST /api/webhook/barn-outreach                              │
│      → Validates X-Webhook-Secret header                        │
│      → Sends email via SMTP channel                             │
│                                                                 │
│  IMAP Listener:                                                 │
│    → Polls inbox for replies                                    │
│    → Matches replies to conversations by thread/APN             │
│    → Runs barn-outreach skill for AI follow-up                  │
│    → POSTs reply data back to BARN-scan webhook                 │
│                                                                 │
│  Skill Engine:                                                  │
│    → Loads barn-outreach-skill/SKILL.md                         │
│    → Applies behavioral rules, Q&A, escalation logic            │
│    → Generates contextual AI responses                          │
│                                                                 │
│  Channels:                                                      │
│    ┌──────────┐    ┌──────────┐                                 │
│    │   SMTP   │    │   IMAP   │                                 │
│    │ (outbound│    │ (inbound │                                 │
│    │  email)  │    │  replies)│                                 │
│    └────┬─────┘    └────┬─────┘                                 │
│         │               │                                       │
└─────────┼───────────────┼───────────────────────────────────────┘
          │               │
          ▼               │
   ┌──────────────┐       │
   │ Owner Inbox  │───────┘
   │              │  (owner replies)
   └──────────────┘
```

---

## 1. Install OpenClaw

### Option A: npm (recommended)

```bash
npm install -g openclaw@latest
openclaw --version
```

### Option B: Docker

```bash
docker pull openclaw/openclaw:latest
docker run -d \
  --name openclaw \
  --env-file .env \
  -p 3100:3100 \
  openclaw/openclaw:latest
```

### Option C: From source

```bash
git clone https://github.com/openclaw/openclaw.git
cd openclaw
npm install
npm run build
```

---

## 2. Configure the SMTP Channel (Outbound Email)

OpenClaw uses SMTP to send outreach emails on behalf of BARN. Configure these environment variables:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com          # Your SMTP server
SMTP_PORT=587                     # 587 for STARTTLS, 465 for SSL
SMTP_USER=outreach@barnhousing.org
SMTP_PASS=your-app-password       # Use an app password, not your login password
SMTP_FROM="BARN Housing <outreach@barnhousing.org>"
SMTP_SECURE=true                  # true for TLS/SSL
```

### Gmail-Specific Notes

If using Gmail:
1. Enable 2-Factor Authentication on the Google account.
2. Generate an **App Password** at https://myaccount.google.com/apppasswords.
3. Use the app password as `SMTP_PASS`.
4. Set `SMTP_HOST=smtp.gmail.com` and `SMTP_PORT=587`.

### Custom Domain / Transactional Email

For production, consider a dedicated transactional email service:
- **Postmark**: `SMTP_HOST=smtp.postmarkapp.com`, `SMTP_PORT=587`
- **SendGrid**: `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`
- **Amazon SES**: `SMTP_HOST=email-smtp.us-west-2.amazonaws.com`, `SMTP_PORT=587`

Ensure your domain has proper **SPF**, **DKIM**, and **DMARC** DNS records to avoid spam filters.

---

## 3. Configure the IMAP Channel (Inbound Reply Detection)

OpenClaw monitors an IMAP mailbox for replies from property owners:

```bash
# IMAP Configuration
IMAP_HOST=imap.gmail.com          # Your IMAP server
IMAP_PORT=993                     # Standard IMAPS port
IMAP_USER=outreach@barnhousing.org
IMAP_PASS=your-app-password       # Same app password or separate credential
IMAP_TLS=true                     # Use TLS (recommended)
IMAP_POLL_INTERVAL=60             # Check for new mail every N seconds (default: 60)
IMAP_MAILBOX=INBOX                # Mailbox to monitor (default: INBOX)
```

### How Reply Matching Works

OpenClaw matches inbound emails to conversations using:
1. **In-Reply-To / References headers** -- standard email threading.
2. **Subject line matching** -- looks for APN patterns or conversation IDs in subject.
3. **From-address matching** -- matches the sender to a known owner email.

When a reply is matched, OpenClaw:
1. Runs the `barn-outreach` skill to evaluate the reply.
2. Optionally generates an AI follow-up response (if configured for auto-reply).
3. POSTs the reply data to BARN-scan's webhook endpoint.

---

## 4. Install the barn-outreach Skill

Copy the skill into OpenClaw's skills directory:

```bash
# If OpenClaw is installed globally
OPENCLAW_SKILLS_DIR=$(openclaw config get skills_dir)
cp -r /path/to/BARN-scan/openclaw/barn-outreach-skill "$OPENCLAW_SKILLS_DIR/"

# Or specify the path in your config
openclaw skills install ./openclaw/barn-outreach-skill
```

### Docker Volume Mount

If running via Docker, mount the skill directory:

```bash
docker run -d \
  --name openclaw \
  --env-file .env \
  -p 3100:3100 \
  -v /path/to/BARN-scan/openclaw/barn-outreach-skill:/app/skills/barn-outreach-skill \
  openclaw/openclaw:latest
```

### Verify Skill Installation

```bash
openclaw skills list
# Should show:
#   barn-outreach    Use when handling outreach emails for the BARN Housing caretaker program
```

---

## 5. Configure the Webhook Connection

OpenClaw and BARN-scan communicate via authenticated webhooks in both directions.

### OpenClaw Environment Variables

```bash
# BARN-scan connection
BARN_SCAN_URL=http://localhost:5000   # BARN-scan base URL
BARN_WEBHOOK_SECRET=your-shared-secret-here  # Must match BARN-scan's setting
```

### BARN-scan Configuration

In the BARN-scan web UI, navigate to **Outreach > Settings** and configure:

| Setting | Value |
|---------|-------|
| `openclaw_gateway_url` | `http://localhost:3100` (or your OpenClaw host) |
| `openclaw_webhook_secret` | Same value as `BARN_WEBHOOK_SECRET` above |
| `smtp_from_address` | `outreach@barnhousing.org` |

These settings are stored in the `outreach_settings` table in Supabase.

Alternatively, set them via the API:

```bash
curl -X POST http://localhost:5000/api/outreach/settings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -d '{
    "openclaw_gateway_url": "http://localhost:3100",
    "openclaw_webhook_secret": "your-shared-secret-here",
    "smtp_from_address": "outreach@barnhousing.org"
  }'
```

### Webhook Secret Generation

Generate a strong shared secret:

```bash
# Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Using Python
python -c "import secrets; print(secrets.token_hex(32))"

# Using OpenSSL
openssl rand -hex 32
```

Use the same secret value in both `BARN_WEBHOOK_SECRET` (OpenClaw) and `openclaw_webhook_secret` (BARN-scan settings).

---

## 6. Environment Variables Reference

### OpenClaw Gateway

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | Yes | -- | SMTP server hostname |
| `SMTP_PORT` | Yes | -- | SMTP server port (587 for STARTTLS, 465 for SSL) |
| `SMTP_USER` | Yes | -- | SMTP authentication username |
| `SMTP_PASS` | Yes | -- | SMTP authentication password or app password |
| `SMTP_FROM` | Yes | -- | From address for outbound emails (e.g., `"BARN Housing <outreach@barnhousing.org>"`) |
| `SMTP_SECURE` | No | `true` | Enable TLS/SSL for SMTP |
| `IMAP_HOST` | Yes | -- | IMAP server hostname |
| `IMAP_PORT` | Yes | `993` | IMAP server port |
| `IMAP_USER` | Yes | -- | IMAP authentication username |
| `IMAP_PASS` | Yes | -- | IMAP authentication password or app password |
| `IMAP_TLS` | No | `true` | Enable TLS for IMAP |
| `IMAP_POLL_INTERVAL` | No | `60` | Seconds between inbox checks |
| `IMAP_MAILBOX` | No | `INBOX` | IMAP mailbox to monitor |
| `BARN_SCAN_URL` | Yes | -- | BARN-scan base URL (e.g., `http://localhost:5000`) |
| `BARN_WEBHOOK_SECRET` | Yes | -- | Shared secret for webhook authentication |
| `OPENCLAW_PORT` | No | `3100` | Port for the OpenClaw HTTP server |
| `OPENCLAW_LOG_LEVEL` | No | `info` | Log level: `debug`, `info`, `warn`, `error` |

### BARN-scan (Outreach Settings in Supabase)

| Key | Required | Description |
|-----|----------|-------------|
| `openclaw_gateway_url` | Yes | OpenClaw base URL (e.g., `http://localhost:3100`) |
| `openclaw_webhook_secret` | Yes | Must match `BARN_WEBHOOK_SECRET` in OpenClaw |
| `smtp_from_address` | No | From address for logging purposes (default: `outreach@barnhousing.org`) |

---

## 7. Testing the Integration

### Step 1: Verify OpenClaw is Running

```bash
curl http://localhost:3100/health
# Expected: {"status": "ok", "version": "x.x.x"}
```

### Step 2: Verify Skill is Loaded

```bash
curl http://localhost:3100/api/skills
# Should include "barn-outreach" in the response
```

### Step 3: Test SMTP (Send a Test Email)

```bash
curl -X POST http://localhost:3100/api/test/smtp \
  -H "Content-Type: application/json" \
  -d '{
    "to": "your-test-email@example.com",
    "subject": "OpenClaw SMTP Test",
    "body": "If you receive this, SMTP is configured correctly."
  }'
```

### Step 4: Test the Webhook Roundtrip

From BARN-scan, trigger a test send:

```bash
# 1. Ensure a property has a pitch draft and owner email
# 2. Send via the BARN-scan API:
curl -X POST http://localhost:5000/api/outreach/TEST-APN-000/send \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT"

# 3. Check BARN-scan logs for the outbound message
# 4. Reply to the email from the test inbox
# 5. Check BARN-scan for the inbound webhook:
curl http://localhost:5000/api/outreach/TEST-APN-000 \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT"
# Should show messages with both outbound and inbound entries
```

### Step 5: Test Webhook Authentication

Verify that unauthenticated requests are rejected:

```bash
# Should return 401
curl -X POST http://localhost:5000/api/outreach/webhook/reply \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: wrong-secret" \
  -d '{"apn": "test", "content": "test"}'
```

---

## Troubleshooting

### Emails Not Sending

1. Check OpenClaw logs: `openclaw logs` or `docker logs openclaw`.
2. Verify SMTP credentials by sending a test email (Step 3 above).
3. Ensure the destination email isn't blocking -- check spam folders.
4. Verify `openclaw_gateway_url` is reachable from BARN-scan.

### Replies Not Detected

1. Verify IMAP credentials and that the mailbox is accessible.
2. Check `IMAP_POLL_INTERVAL` -- replies won't appear instantly.
3. Confirm the reply is going to the monitored mailbox (check `IMAP_MAILBOX`).
4. Look at OpenClaw logs for IMAP connection errors.

### Webhook Failures

1. Ensure `BARN_WEBHOOK_SECRET` matches `openclaw_webhook_secret` exactly.
2. Verify BARN-scan is reachable from OpenClaw at `BARN_SCAN_URL`.
3. Check BARN-scan logs for 401 errors (secret mismatch) or 400 errors (missing `apn`).

### Skill Not Found

1. Run `openclaw skills list` to verify installation.
2. Check that the skill directory contains `SKILL.md` with the correct frontmatter.
3. Restart OpenClaw after installing a new skill.
