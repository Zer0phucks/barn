-- BARN baseline, 5/6: the read contract shared by Flask and Android.
--
-- Retired here, versus the prior barn schema:
--   * get_bills_for_map()                    -> the map_markers view
--   * android_get_next_scoutable_property()  -> scout_next()
--   * get_bills_filtered()                   -> PostgREST querying map_markers
--     directly. It took 15 scalar parameters and reimplemented, in plpgsql,
--     filtering that PostgREST already does from the query string.
--
-- The old nearest-property RPC ranked candidates with a hand-rolled haversine
-- (`power(sin(radians(...)))`) over a full table scan. scout_next() below uses
-- a PostGIS `<->` KNN ordering against idx_bills_geom instead: same semantics,
-- same parameters, index-backed.

-- ---------------------------------------------------------------------------
-- map_markers: one row shape for the web map, the properties list, and the
-- Android map. Normalizes is_scouted to a real boolean via a join, replacing
-- the old split where Flask did Python set-membership and SQL did a JOIN and
-- the two could disagree.
-- ---------------------------------------------------------------------------

create view map_markers as
select
  b.apn,
  b.location_of_property as location,
  b.city,
  b.zip_code,
  b.power_status,
  b.has_vpt,
  b.vpt_marker,
  b.delinquent,
  b.tax_year,
  b.last_payment,
  b.bill_url,
  b.condition_score,
  b.streetview_image_path,
  b.research_status,
  b.ai_vacancy_verdict,
  b.owner_name,
  b.deceased_count,
  b.outreach_score,
  b.outreach_stage,
  b.added_at,
  b.lat,
  b.lng,
  -- Mailing address and situs zip live in the raw county export, not on bills.
  -- Note the lowercase p.apn: the old schema quoted this as p."APN", which is
  -- exactly the sort of thing this baseline exists to remove.
  (p.row_json ->> 'MailingAddress') as mailing_address,
  (p.row_json ->> 'SitusZip')       as situs_zip,
  (sr.apn is not null)              as is_scouted
from bills b
left join parcels p on p.apn = b.apn
left join lateral (
  select 1 as apn from scout_results s where s.apn = b.apn limit 1
) sr on true
where b.lat is not null and b.lng is not null;

grant select on map_markers to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- scout_next: nearest unscouted property matching the active filters.
-- Called identically by Flask (service_role) and Android (authenticated).
-- ---------------------------------------------------------------------------

create function public.scout_next(
  p_lat           double precision,
  p_lng           double precision,
  p_city          text             default null,
  p_q             text             default null,
  p_vpt_only      boolean          default false,
  p_list_id       bigint           default null,
  p_condition_min double precision default null,
  p_condition_max double precision default null,
  p_limit         int              default 1
) returns table (
  apn                   text,
  address               text,
  city                  text,
  has_vpt               int,
  condition_score       double precision,
  streetview_image_path text,
  latitude              double precision,
  longitude             double precision,
  distance_km           double precision,
  remaining             bigint
) language sql stable as $$
  with candidates as (
    select b.apn, b.location_of_property as address, b.city, b.has_vpt,
           b.condition_score, b.streetview_image_path, b.lat, b.lng, b.geom
    from bills b
    where b.geom is not null
      and not exists (select 1 from scout_results sr where sr.apn = b.apn)
      and (p_city is null or lower(b.city) = lower(p_city))
      and (p_q is null or b.apn ilike '%' || p_q || '%'
                       or b.location_of_property ilike '%' || p_q || '%')
      and (not p_vpt_only or b.has_vpt = 1)
      and (p_condition_min is null or b.condition_score >= p_condition_min)
      and (p_condition_max is null or b.condition_score <= p_condition_max)
      and (p_list_id is null
           or b.apn in (select lp.apn from list_properties lp where lp.list_id = p_list_id))
  )
  select c.apn, c.address, c.city, c.has_vpt, c.condition_score, c.streetview_image_path,
         c.lat, c.lng,
         ST_Distance(c.geom, ST_MakePoint(p_lng, p_lat)::geography) / 1000.0 as distance_km,
         (select count(*) from candidates) - 1 as remaining
  from candidates c
  order by c.geom <-> ST_MakePoint(p_lng, p_lat)::geography
  limit p_limit;
$$;

revoke all on function public.scout_next from public;
grant execute on function public.scout_next to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Route queue helpers. These stay as RPCs rather than becoming client-side
-- writes because both need to assign sort_order values atomically against
-- concurrent edits from the phone and the web UI.
-- ---------------------------------------------------------------------------

create function public.append_properties_to_list(
  p_list_id bigint,
  p_apns    text[]
) returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  next_sort_order integer;
  inserted_count  integer := 0;
  current_apn     text;
begin
  if auth.uid() is null then
    raise exception 'BARN scanner access requires an authenticated session'
      using errcode = '42501';
  end if;

  select coalesce(max(sort_order) + 1, 0)
    into next_sort_order
    from list_properties
   where list_id = p_list_id;

  for current_apn in
    with requested as (
      select trim(value) as apn, min(ord) as ord
        from unnest(coalesce(p_apns, array[]::text[])) with ordinality as u(value, ord)
       where trim(value) <> ''
       group by trim(value)
    )
    select apn from requested order by ord
  loop
    if exists (
      select 1 from list_properties
       where list_id = p_list_id and apn = current_apn
    ) then
      continue;
    end if;

    insert into list_properties (list_id, apn, sort_order)
    values (p_list_id, current_apn, next_sort_order)
    on conflict (list_id, apn) do update set sort_order = excluded.sort_order;

    next_sort_order := next_sort_order + 1;
    inserted_count  := inserted_count + 1;
  end loop;

  return inserted_count;
end;
$$;

revoke all on function public.append_properties_to_list(bigint, text[]) from public;
grant execute on function public.append_properties_to_list(bigint, text[]) to authenticated, service_role;

-- Reorders to match p_apns, then appends any list members p_apns omitted so no
-- property silently loses its place.
create function public.reorder_list_properties(
  p_list_id bigint,
  p_apns    text[]
) returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  existing_apns  text[];
  requested_apns text[];
  current_apn    text;
  next_order     integer := 0;
  updated_count  integer := 0;
begin
  if auth.uid() is null then
    raise exception 'BARN scanner access requires an authenticated session'
      using errcode = '42501';
  end if;

  select coalesce(array_agg(apn order by sort_order, apn), array[]::text[])
    into existing_apns
    from list_properties
   where list_id = p_list_id;

  if coalesce(array_length(existing_apns, 1), 0) = 0 then
    return 0;
  end if;

  with requested as (
    select trim(value) as apn, min(ord) as ord
      from unnest(coalesce(p_apns, array[]::text[])) with ordinality as u(value, ord)
     where trim(value) <> ''
     group by trim(value)
  )
  select coalesce(array_agg(apn order by ord), array[]::text[])
    into requested_apns
    from requested
   where apn = any(existing_apns);

  foreach current_apn in array requested_apns loop
    update list_properties
       set sort_order = next_order
     where list_id = p_list_id and apn = current_apn;
    next_order    := next_order + 1;
    updated_count := updated_count + 1;
  end loop;

  foreach current_apn in array existing_apns loop
    if current_apn = any(requested_apns) then
      continue;
    end if;
    update list_properties
       set sort_order = next_order
     where list_id = p_list_id and apn = current_apn;
    next_order    := next_order + 1;
    updated_count := updated_count + 1;
  end loop;

  return updated_count;
end;
$$;

revoke all on function public.reorder_list_properties(bigint, text[]) from public;
grant execute on function public.reorder_list_properties(bigint, text[]) to authenticated, service_role;
