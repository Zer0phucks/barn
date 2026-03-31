-- Fix zip code filtering in get_bills_filtered.
-- Previous version only checked b.location_of_property (which rarely contains zip codes)
-- and b.apn LIKE p_zip||'%' (APNs are not zip-prefixed).
-- This version checks parcels.row_json->>'SitusZip' and 'MailingZip', and also handles
-- comma-separated zip values (multi-select from the UI dropdown).

CREATE OR REPLACE FUNCTION public.get_bills_filtered(
    p_q TEXT DEFAULT '',
    p_zip TEXT DEFAULT '',
    p_power TEXT DEFAULT '',
    p_city TEXT DEFAULT '',
    p_vpt INTEGER DEFAULT -1,
    p_delinquent INTEGER DEFAULT -1,
    p_condition TEXT DEFAULT '',
    p_outofstate INTEGER DEFAULT -1,
    p_fav INTEGER DEFAULT -1,
    p_sort TEXT DEFAULT 'location_of_property',
    p_order TEXT DEFAULT 'asc',
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0,
    p_research TEXT DEFAULT '',
    p_owner_name TEXT DEFAULT ''
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    result JSON;
BEGIN
    WITH filtered AS (
        SELECT b.*, p.row_json
        FROM public.bills b
        LEFT JOIN public.parcels p ON p."APN" = b.apn
        WHERE
            (p_q = '' OR p_q IS NULL OR b.location_of_property ILIKE '%' || p_q || '%' OR b.apn ILIKE '%' || p_q || '%' OR b.owner_name ILIKE '%' || p_q || '%')
            AND (p_zip = '' OR p_zip IS NULL OR
                EXISTS (
                    SELECT 1 FROM unnest(string_to_array(p_zip, ',')) AS z(val)
                    WHERE
                        b.location_of_property ILIKE '%' || trim(z.val) || '%'
                        OR (p.row_json->>'SitusZip') ILIKE '%' || trim(z.val) || '%'
                        OR (p.row_json->>'MailingZip') ILIKE '%' || trim(z.val) || '%'
                )
            )
            AND (p_power = '' OR p_power IS NULL OR b.power_status = p_power)
            AND (p_city = '' OR p_city IS NULL OR LOWER(b.city) = LOWER(p_city))
            AND (p_vpt = -1 OR p_vpt IS NULL OR b.has_vpt = p_vpt)
            AND (p_delinquent = -1 OR p_delinquent IS NULL OR b.delinquent = p_delinquent)
            AND (p_condition = '' OR p_condition IS NULL OR (
                CASE
                    WHEN p_condition = 'good' THEN b.condition_score >= 7
                    WHEN p_condition = 'fair' THEN b.condition_score >= 4 AND b.condition_score < 7
                    WHEN p_condition = 'poor' THEN b.condition_score < 4
                    WHEN p_condition = 'unscored' THEN b.condition_score IS NULL
                    ELSE true
                END
            ))
            AND (p_fav = -1 OR p_fav IS NULL OR (p_fav = 1 AND EXISTS (SELECT 1 FROM public.favorites f WHERE f.apn = b.apn)))
            AND (p_research = '' OR p_research IS NULL OR (
                CASE
                    WHEN p_research = 'completed' THEN b.research_status = 'completed'
                    WHEN p_research = 'unchecked' THEN b.research_status IS NULL OR b.research_status = 'unchecked'
                    ELSE b.research_status = p_research
                END
            ))
            AND (p_owner_name = '' OR p_owner_name IS NULL OR b.owner_name ILIKE '%' || p_owner_name || '%')
    ),
    counted AS (
        SELECT COUNT(*) AS total FROM filtered
    ),
    paged AS (
        SELECT f.* FROM filtered f, counted c
        ORDER BY
            CASE WHEN p_order = 'asc' AND p_sort = 'added_at' THEN f.added_at END ASC NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'added_at' THEN f.added_at END DESC NULLS LAST,
            CASE WHEN p_order = 'asc' AND p_sort = 'city' THEN f.city END ASC NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'city' THEN f.city END DESC NULLS LAST,
            CASE WHEN p_order = 'asc' THEN f.location_of_property END ASC NULLS LAST,
            CASE WHEN p_order = 'desc' THEN f.location_of_property END DESC NULLS LAST
        LIMIT p_limit OFFSET p_offset
    )
    SELECT json_build_object(
        'rows', COALESCE(json_agg(paged), '[]'::json),
        'total', (SELECT total FROM counted)
    ) INTO result
    FROM paged;

    RETURN result;
END;
$$;
