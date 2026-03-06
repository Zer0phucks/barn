# BARN-scan Outreach Pipeline Design

**Date:** 2026-03-02
**Status:** Approved
**Approach:** Outreach CRM Lite + OpenClaw AI Agent

## Context

BARN Housing (barnhousing.org) operates a caretaker program for vacant properties in Alameda County, CA. Property owners grant access to BARN, which rehabs the property and places a caretaker (a homeless person in need of housing) to watch over it. This saves the owner from paying Vacant Property Tax (VPT), allows them to write off fair market rent as a charitable donation, and since caretakers are there for work (not as tenants), owners avoid eviction hassles if they want to rent normally again.

BARN-scan already identifies vacant/delinquent properties, collects owner contacts, and generates AI research reports. What's missing is the ability to actually reach out to owners, track conversations, and move them through a partnership pipeline.

## Architecture Overview

```
BARN-scan (Flask + Supabase)          OpenClaw (Gateway)
┌──────────────────────────┐          ┌──────────────────────────┐
│ Outreach Pipeline UI     │─webhook─→│ AI Agent                 │
│ Scoring Engine           │          │  - BARN outreach skill   │
│ Pitch Draft Generator    │          │  - Caretaker program FAQ │
│ Communication Log        │←webhook──│  - Escalation rules      │
│ Outreach Dashboard       │          │                          │
└──────────────────────────┘          │ Channels:                │
         ↕                            │  - SMTP (outbound email) │
    Supabase DB                       │  - IMAP (inbound replies)│
                                      │  - WhatsApp (future)     │
                                      └──────────────────────────┘
```

## 1. Outreach Readiness Scoring

Composite score (0-100) ranking properties by outreach priority.

| Signal | Weight | Logic |
|--------|--------|-------|
| Has owner email | 25 | Required for email outreach. No email = score capped at 30. |
| VPT status (has_vpt=true) | 20 | Owner is paying VPT -- strongest pain point for the caretaker pitch. |
| Delinquent on taxes | 15 | Financially motivated owner, more likely to engage. |
| Power off | 15 | Strong vacancy indicator -- property is sitting empty. |
| Condition score < 5.0 | 10 | Deteriorating property -- owner may want someone maintaining it. |
| Out-of-state owner | 10 | Absentee owners are more likely to want a hands-off solution. |
| Research completed | 5 | We have deep context for a personalized pitch. |

Stored as `outreach_score` on the `bills` table. Recalculated when underlying data changes. Filterable and sortable in all views.

## 2. Pipeline Stages

```
Identified → Qualified → Outreach Ready → Contacted → Responding → Negotiating → Partnered
                                              ↓            ↓            ↓
                                           No Response   Declined     Declined
```

| Stage | Meaning | Trigger |
|-------|---------|---------|
| Identified | VPT scanner found the property | Automatic (scan) |
| Qualified | Outreach score >= 50 | Automatic (score calc) |
| Outreach Ready | Has email + research complete + pitch drafted | Automatic |
| Contacted | First outreach email sent | OpenClaw sends email |
| Responding | Owner has replied | OpenClaw detects reply |
| Negotiating | Owner expressed interest in caretaker program | Manual or AI-flagged |
| Partnered | Agreement reached | Manual |
| Declined | Owner said no or asked to stop | Manual or AI-detected |
| No Response | No reply after follow-up sequence exhausted | Automatic (after 21 days) |

### Database: `outreach` table

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| apn | text | FK to bills |
| stage | text | Pipeline stage enum |
| outreach_score | float | Cached score |
| pitch_draft | text | AI-generated email text |
| pitch_subject | text | AI-generated subject line |
| contacted_at | timestamp | When first email was sent |
| last_response_at | timestamp | When last reply was received |
| next_followup_at | timestamp | When next follow-up is due |
| followup_count | int | Number of follow-ups sent |
| notes | text | Free-text notes |
| openclaw_session_id | text | Links to OpenClaw conversation |
| created_at | timestamp | Record creation |
| updated_at | timestamp | Last modification |

### Database: `outreach_messages` table

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| apn | text | FK to bills |
| direction | text | inbound / outbound |
| channel | text | email / whatsapp / phone |
| subject | text | Email subject (if applicable) |
| content | text | Message body |
| from_address | text | Sender |
| to_address | text | Recipient |
| sent_at | timestamp | When sent/received |
| openclaw_message_id | text | OpenClaw reference |

## 3. AI Pitch Generation

For each "Outreach Ready" property, Gemini generates a personalized first-contact email.

### Input to AI

- Property details: address, VPT amount, delinquency status, condition score
- Owner details: name, mailing address, out-of-state status
- Research report (if available)
- BARN caretaker program details (static context)

### Output

- **Subject line**: Personalized, professional (e.g., "Your property at 1234 Oak St -- a way to save on the Vacant Property Tax")
- **Email body** covering:
  1. Acknowledge their situation (VPT charges, vacant property)
  2. Introduce BARN Housing as a local nonprofit
  3. Explain the caretaker program: BARN rehabs the property, places a caretaker, owner saves VPT, gets a tax write-off for fair market rent value
  4. Emphasize: caretakers are not tenants, no eviction risk, owner retains full control
  5. Clear call to action (reply to learn more, or schedule a call)
- **Tone**: Professional, warm, nonprofit voice. Not salesy or pushy.

### Review Flow

All drafts stored in the `outreach` table. User can review/edit before sending. Optional "auto-send" for leads above a configurable score threshold.

## 4. OpenClaw Integration

### Outbound Flow

1. BARN-scan marks a property "Outreach Ready" with a generated pitch draft
2. User clicks "Send Outreach" (or auto-send triggers)
3. BARN-scan sends webhook to OpenClaw: owner email, pitch draft, property context
4. OpenClaw agent sends email via direct SMTP
5. BARN-scan logs the message and updates pipeline stage to "Contacted"

### Inbound Flow (Reply Handling)

1. OpenClaw polls IMAP inbox for replies to the outreach address
2. AI agent reads the reply with full caretaker program context
3. Agent responds conversationally:
   - Answers questions about the program
   - Addresses concerns (tenancy, legal, timeline)
   - If owner shows interest → webhook to BARN-scan → stage "Negotiating"
   - If owner declines → webhook to BARN-scan → stage "Declined"
   - If complex/sensitive question → escalates to human via notification
4. All messages logged back to BARN-scan via webhook

### Follow-up Automation

- Day 7: Gentler follow-up if no reply
- Day 14: Final "just checking in" message
- Day 21: Move to "No Response" stage

### OpenClaw Skill

Custom skill at `~/.openclaw/workspace/skills/barn-outreach/SKILL.md` containing:
- Full caretaker program details and FAQ
- Tone and voice guidelines
- Escalation rules (when to hand off to human)
- API access patterns for looking up property details

### Email Configuration

- **Outbound**: Direct SMTP (e.g., outreach@barnhousing.org)
- **Inbound**: IMAP polling for reply detection
- **Deliverability**: SPF/DKIM configured on barnhousing.org domain

## 5. Web UI Changes

### New "Outreach" Tab

- **Funnel summary**: Counts per pipeline stage
- **Pipeline table**: Sortable by outreach score, stage, days since last contact
- **Quick actions**: Generate Pitch, Review Draft, Send, Mark Declined
- **Filters**: By stage, score range, city, date ranges

### Property Detail Page Additions

- **Outreach section**: Current stage, score breakdown, pitch draft (editable), communication history timeline
- **"Send Outreach" button**: Triggers the OpenClaw flow
- **Message timeline**: All outreach messages for this property

### Admin: Outreach Settings

- SMTP configuration (host, port, from address, credentials)
- OpenClaw Gateway URL and webhook secret
- Auto-send score threshold
- Follow-up schedule (days between, max count)
- Email signature / footer template

## 6. Data Quality Improvements

### Contact Completeness Score

Per-property score (0-100%):
- Has email: 40%
- Has phone: 20%
- Has mailing address: 20%
- Has owner name: 20%

Surfaced in UI. Properties with high outreach value but low completeness are flagged for re-scanning.

### Auto-Triggered Scanner Pipeline

```
VPT Scan (finds property) → Contact Scan (gets owner info) → Research Scan (deep context) → Pitch Generation → Outreach
```

Each stage auto-triggers the next when a property meets the threshold.

### Owner Deduplication

Group properties by owner (matched by name, email, or mailing address). Send one consolidated email per owner covering all their vacant properties rather than separate emails per APN.
