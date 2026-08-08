-- BARN baseline, 6/6: row level security and the image bucket.
--
-- Threat model: a small shared team, no per-user ownership. Policies gate on
-- "is signed in", not on row ownership. The scanners and the Flask admin UI
-- connect with the service role, which bypasses RLS entirely — so the policies
-- below exist to constrain the Android app and anything else holding only the
-- publishable key.
--
-- Back-office tables (outreach*, cbc_image_extractions, scanner_*) get RLS
-- enabled with NO policies. That is deliberate, not an omission: it makes them
-- unreachable with a publishable key while staying fully available to the
-- service role.

alter table bills           enable row level security;
alter table parcels         enable row level security;
alter table lists           enable row level security;
alter table list_properties enable row level security;
alter table scout_results   enable row level security;

-- Reference data: readable by any signed-in user, written only by scanners.
create policy bills_select_authenticated on bills
  for select to authenticated using (true);

create policy parcels_select_authenticated on parcels
  for select to authenticated using (true);

-- Scouting data: signed-in users create and edit it from the field.
create policy lists_rw_authenticated on lists
  for all to authenticated using (true) with check (true);

create policy list_properties_rw_authenticated on list_properties
  for all to authenticated using (true) with check (true);

create policy scout_results_rw_authenticated on scout_results
  for all to authenticated using (true) with check (true);

-- Back office: service role only (no policies by design, see header).
alter table outreach                enable row level security;
alter table outreach_messages       enable row level security;
alter table outreach_settings       enable row level security;
alter table cbc_image_extractions   enable row level security;
alter table scanner_workers         enable row level security;
alter table scanner_jobs            enable row level security;
alter table scanner_job_checkpoints enable row level security;

-- ---------------------------------------------------------------------------
-- Street View / satellite imagery bucket.
--
-- Public read: the Android app renders these directly from
-- bills.streetview_image_path, and they are photos of building exteriors from
-- public imagery APIs, not sensitive material. Writes are service-role only
-- (condition_scanner.py, backfill_streetview.py) because no policies are
-- created for the insert/update/delete verbs.
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('streetview-images', 'streetview-images', true)
on conflict (id) do nothing;

create policy streetview_images_public_read on storage.objects
  for select to public using (bucket_id = 'streetview-images');
