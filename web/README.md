# BARN Housing Platform

BARN (Bay Area Renewal Network) is a React + Supabase web app for identifying vacant properties, partnering with owners, coordinating volunteers, reviewing housing applications, and processing donations.

## Features

- Public forms for:
  - reporting abandoned properties
  - property owner registration and authorization
  - volunteer signup
  - housing/caretaker applications
- Admin dashboard for reviewing and updating submissions
- Admin-authenticated access control using Supabase Auth + role checks
- Donation checkout flow via Supabase Edge Function + Stripe
- VPT Scanner section integrated directly with Supabase scanner tables/RPCs

## Tech Stack

- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Supabase (Postgres, Auth, Storage, Edge Functions)
- Stripe Checkout (donations)
- Vitest + Testing Library

## App Routes

- `/`: marketing homepage and action modals
- `/report-property`: detailed report-property page
- `/register-property`: owner onboarding page
- `/volunteer`: volunteer page
- `/apply-housing`: housing application page
- `/admin`: admin sign-in/sign-up
- `/admin/dashboard`: admin management dashboard
- `/donation-success`: post-checkout success page

## Local Development

### Prerequisites

- Node.js 18+ and npm
- Supabase project with this schema applied

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment variables

Create `.env.local` (or `.env`):

```bash
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_PUBLISHABLE_KEY=your_supabase_anon_or_publishable_key
# Optional
VITE_SUPABASE_PROJECT_ID=your_project_ref
```

### 3. Run development server

```bash
npm run dev
```

Vite is configured to run at `http://localhost:8080`.

### 4. Build, lint, test

```bash
npm run build
npm run lint
npm run test
```

## Supabase Setup

Migrations in `supabase/migrations` create:

- `property_reports`
- `volunteers`
- `housing_applications`
- `owner_registrations`
- `user_roles`
- helper functions `has_role` and `is_admin`
- private storage bucket `owner-documents`

Apply migrations:

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push
```

### Grant admin access

After creating a user through `/admin`, assign the admin role in Supabase SQL Editor:

```sql
insert into public.user_roles (user_id, role)
values ('<auth_user_uuid>', 'admin')
on conflict (user_id, role) do nothing;
```

## Donations (Stripe)

The donation UI invokes Supabase Edge Function `create-donation` in `supabase/functions/create-donation`.

1. Set Stripe secret:

```bash
supabase secrets set STRIPE_SECRET_KEY=sk_test_or_live_key
```

2. Deploy function:

```bash
supabase functions deploy create-donation --no-verify-jwt
```

3. Set allowed origins for CORS:

```bash
supabase secrets set ALLOWED_ORIGINS="https://your-domain.com,http://localhost:8080"
```

If the donate flow returns `Missing STRIPE_SECRET_KEY`, the edge function is deployed but Stripe is not configured yet.

## VPT Scanner (Unified Mode)

The `VPT Scanner` tab now reads data directly from Supabase (`bills`, `favorites`, `parcels`) using scanner RPCs (`get_bills_filtered`, `get_bills_for_map`).

Notes:
- No separate VPT web login is required inside BARN admin.
- Favorites toggle and scanner filters are handled directly in Supabase.
- Scanner control actions call Supabase Edge Function `vpt-scanner-control`, which forwards to a scanner worker API.

Configure scanner worker forwarding:

```bash
supabase secrets set VPT_WORKER_BASE_URL="https://your-scanner-worker.example.com"
supabase secrets set VPT_WORKER_API_KEY="your_worker_api_key"
supabase functions deploy vpt-scanner-control
```

The worker URL must be a scanner runtime that can execute scan jobs (not just a static/web-only deployment). If the worker returns errors like `No module named 'scanner'`, the runtime does not include scanner modules.

Optional browser-side fallback (local development):

```bash
VITE_VPT_WORKER_BASE_URL=http://localhost:5000
VITE_VPT_WORKER_API_KEY=your_worker_api_key
```

## Project Structure

```text
src/
  components/             reusable UI, forms, and admin tables
  pages/                  route-level pages
  services/vptApi.ts      Supabase-backed VPT scanner client
  integrations/supabase/  Supabase client and generated types
supabase/
  migrations/             schema, RLS policies, and helper SQL
  functions/create-donation/  Stripe checkout edge function
  functions/vpt-scanner-control/  scanner worker forwarding edge function
```
