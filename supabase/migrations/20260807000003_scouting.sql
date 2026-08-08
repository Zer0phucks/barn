-- BARN baseline, 3/6: lists and field scouting.
--
-- Deliberately absent, versus the two prior schemas:
--   * `favorites` — was a parallel one-off of list_properties. A list literally
--     named 'Favorites' does the same job, and the old schema already shipped a
--     favorites -> lists data migration. One mechanism, not two.
--   * `scouting_collections` / `collection_properties` — dead code in both the
--     Flask app and the Android app. The Kotlin side already aliases
--     "Collection" onto list operations (Repositories.kt).

create table lists (
  id          bigint generated always as identity primary key,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table list_properties (
  id         bigint generated always as identity primary key,
  list_id    bigint not null references lists(id) on delete cascade,
  apn        text   not null references bills(apn) on delete cascade,
  sort_order int    not null default 0,
  created_at timestamptz not null default now(),
  unique (list_id, apn)
);

create index idx_list_properties_list on list_properties (list_id, sort_order);
create index idx_list_properties_apn  on list_properties (apn);

-- One row per physical visit. A property is "scouted" iff a row exists here,
-- which is what map_markers.is_scouted and scout_next()'s exclusion both use.
create table scout_results (
  id         bigint generated always as identity primary key,
  apn        text    not null references bills(apn) on delete cascade,
  list_id    bigint  references lists(id) on delete set null,
  follow_up  boolean not null,
  flyered    boolean not null,
  notes      text,
  latitude   double precision,
  longitude  double precision,
  scouted_by uuid references auth.users(id),
  scouted_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index idx_scout_results_apn  on scout_results (apn);
create index idx_scout_results_list on scout_results (list_id);
create index idx_scout_results_time on scout_results (scouted_at desc);

-- Seed the replacement for the old favorites table so the UI has somewhere to
-- put one-off saves on a fresh database.
insert into lists (name, description)
values ('Favorites', 'Ad-hoc saved properties')
on conflict do nothing;
