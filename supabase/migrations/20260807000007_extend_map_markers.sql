-- Extend map_markers so it can serve BOTH remaining direct-table readers:
--
--   * Flask's /api/markers, which needs parcel_number, tracer_number,
--     situs_address, the two search URLs, and is_favorite.
--   * The Android app's Property model, which needs last_sale_date and
--     is_out_of_state.
--
-- With these present, neither client has to re-derive coordinates from parcel
-- centroids or issue a second query against parcels.
--
-- CREATE OR REPLACE VIEW cannot insert columns mid-list, so this drops and
-- recreates. Nothing depends on the view besides the two callers above.

drop view if exists map_markers;

create view map_markers as
select
  b.apn,
  b.location_of_property as location,
  b.parcel_number,
  b.tracer_number,
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
  b.prop_last_sale_date as last_sale_date,
  b.property_search_url,
  b.mailing_search_url,
  b.outreach_score,
  b.outreach_stage,
  b.added_at,
  b.lat,
  b.lng,
  (p.row_json ->> 'MailingAddress') as mailing_address,
  (p.row_json ->> 'SitusAddress')   as situs_address,
  (p.row_json ->> 'SitusZip')       as situs_zip,
  -- Owner mails somewhere outside California. Blank state is treated as local,
  -- matching the existing filter in scan/db.py.
  (
    coalesce(nullif(upper(trim(p.row_json ->> 'MailState')), ''), 'CA') <> 'CA'
  ) as is_out_of_state,
  (fav.apn is not null) as is_favorite,
  (sr.apn is not null)  as is_scouted
from bills b
left join parcels p on p.apn = b.apn
left join lateral (
  select 1 as apn
  from scout_results s
  where s.apn = b.apn
  limit 1
) sr on true
-- Favorites is an ordinary list now, so is_favorite is a join rather than a
-- separate table. Resolved by name to avoid hardcoding an id.
left join lateral (
  select 1 as apn
  from list_properties lp
  join lists l on l.id = lp.list_id
  where lp.apn = b.apn and l.name = 'Favorites'
  limit 1
) fav on true
where b.lat is not null and b.lng is not null;

grant select on map_markers to authenticated, service_role;
