-- BARN baseline, 2/6: parcels + bills.
--
-- parcels is the raw county CSV import, one row per APN, kept as jsonb so new
-- export columns don't require a migration. bills is the working table: one
-- row per property we've scraped, enriched, and scouted.

-- ---------------------------------------------------------------------------
-- parcels
-- ---------------------------------------------------------------------------

create table parcels (
  apn        text primary key,
  row_json   jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table parcels is
  'Raw county parcel export, one row per APN. row_json holds the full CSV row; '
  'centroids arrive as CENTROID_X/Y or X_CORD/Y_CORD in EPSG:3857 (see scan/geo_utils.py).';

-- ---------------------------------------------------------------------------
-- bills
-- ---------------------------------------------------------------------------

create table bills (
  apn                   text primary key,

  -- Tax portal scrape (find_meas_w_addresses.py)
  parcel_number         text,
  tracer_number         text,
  location_of_property  text,
  city                  text,
  zip_code              text,
  tax_year              text,
  last_payment          text,
  delinquent            integer not null default 0,
  has_vpt               integer not null default 0,
  vpt_marker            text,
  bill_url              text,
  raw_text              text,
  pdf_file              text,
  added_at              timestamptz not null default now(),

  -- Geo. geom is derived from lat/lng by trigger, never written directly.
  lat                   double precision,
  lng                   double precision,
  geom                  geography(Point, 4326),

  -- Vacancy signals
  power_status          text,
  site_vacant           boolean,
  mail_vacant           boolean,
  condition_score       double precision,
  condition_notes       text,
  condition_updated_at  timestamptz,
  streetview_image_path text,

  -- AI research (gemini_research_scanner.py, cyber_research_agent.py)
  research_status       text,
  research_report_path  text,
  research_updated_at   timestamptz,
  ai_vacancy_verdict    text,
  ai_vacancy_confidence real,
  ai_vacancy_rationale  text,
  ai_vacancy_updated_at timestamptz,

  -- Ownership and contact (contact_scanner.py, populate_search_urls.py)
  owner_name               text,
  owner_email              text,
  owner_phone              text,
  owner_mobile_phone       text,
  owner_contact_status     text,
  owner_contact_updated_at timestamptz,
  owner_occupied           boolean,
  non_owner_occupied       boolean,
  deceased_owner           boolean,
  tenant_verified          boolean,
  contact_completeness     real not null default 0,
  owner_details_url        text,
  property_search_url      text,
  mailing_search_url       text,

  -- CyberBackgroundChecks extraction (ingest_cbc_images_to_supabase.py)
  primary_resident_name text,
  primary_resident_age  text,
  deceased_count        integer,
  important_notes       text,
  cbc_source_image_name text,
  cbc_extracted_address text,
  prop_ownership_type   text,
  prop_last_sale_date   text,
  prop_occupancy_type   text,

  -- Outreach rollup, denormalized from the outreach table for fast filtering
  outreach_score        real not null default 0,
  outreach_stage        text not null default 'identified'
);

comment on column bills.has_vpt is '0/1, not boolean: 1 when a vacant-property-tax marker was found on the bill.';
comment on column bills.ai_vacancy_verdict is 'likely_vacant | likely_occupied | unknown';
comment on column bills.ai_vacancy_confidence is '0.0-1.0 confidence for ai_vacancy_verdict';
comment on column bills.streetview_image_path is
  'Supabase Storage public URL (bucket streetview-images). Must be fetchable by '
  'the Android app, so never a path on the scanner VM disk.';

-- ---------------------------------------------------------------------------
-- Keep geom in sync with lat/lng so no writer has to think about PostGIS.
-- ---------------------------------------------------------------------------

create function bills_set_geom() returns trigger language plpgsql as $$
begin
  if new.lat is not null and new.lng is not null then
    new.geom := ST_SetSRID(ST_MakePoint(new.lng, new.lat), 4326)::geography;
  else
    new.geom := null;
  end if;
  return new;
end;
$$;

create trigger trg_bills_set_geom
  before insert or update of lat, lng on bills
  for each row execute function bills_set_geom();

-- ---------------------------------------------------------------------------
-- Indexes
--
-- The GIST index backs scout_next()'s `geom <->` KNN ordering. The previous
-- schema deliberately deferred it until after a 140k-row backfill; starting
-- empty, there is no reason to wait.
-- ---------------------------------------------------------------------------

create index idx_bills_geom            on bills using gist (geom);
create index idx_bills_city            on bills (city);
create index idx_bills_has_vpt         on bills (has_vpt) where has_vpt = 1;
create index idx_bills_condition_score on bills (condition_score);
create index idx_bills_added_at        on bills (added_at desc);
create index idx_bills_outreach_score  on bills (outreach_score desc);
create index idx_bills_research_status on bills (research_status);
