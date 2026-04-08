-- Allow any authenticated Supabase user to use the Android scanner Phase 1
-- surface while still blocking anonymous access.

-- 1. Property browsing RPC: run with definer privileges, but require an
-- authenticated session.
CREATE OR REPLACE FUNCTION public.get_bills_filtered(
    p_q          TEXT    DEFAULT '',
    p_zip        TEXT    DEFAULT '',
    p_power      TEXT    DEFAULT '',
    p_city       TEXT    DEFAULT '',
    p_vpt        INTEGER DEFAULT -1,
    p_delinquent INTEGER DEFAULT -1,
    p_condition  TEXT    DEFAULT '',
    p_outofstate INTEGER DEFAULT -1,
    p_fav        INTEGER DEFAULT -1,
    p_sort       TEXT    DEFAULT 'location_of_property',
    p_order      TEXT    DEFAULT 'asc',
    p_limit      INTEGER DEFAULT 50,
    p_offset     INTEGER DEFAULT 0,
    p_research   TEXT    DEFAULT '',
    p_owner_name TEXT    DEFAULT '',
    p_new        INTEGER DEFAULT -1
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result JSON;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'BARN scanner access requires an authenticated session'
            USING ERRCODE = '42501';
    END IF;

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
                    WHEN p_condition = 'good'     THEN b.condition_score >= 7
                    WHEN p_condition = 'fair'     THEN b.condition_score >= 4 AND b.condition_score < 7
                    WHEN p_condition = 'poor'     THEN b.condition_score < 4
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
            AND (
                p_new = -1 OR p_new IS NULL
                OR (p_new = 1 AND b.new_reviewed_at IS NULL)
                OR (p_new = 0 AND b.new_reviewed_at IS NOT NULL)
            )
    ),
    counted AS (
        SELECT COUNT(*) AS total FROM filtered
    ),
    paged AS (
        SELECT f.* FROM filtered f, counted c
        ORDER BY
            CASE WHEN p_order = 'asc'  AND p_sort = 'added_at'            THEN f.added_at            END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'added_at'            THEN f.added_at            END DESC NULLS LAST,
            CASE WHEN p_order = 'asc'  AND p_sort = 'city'                THEN f.city                END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'city'                THEN f.city                END DESC NULLS LAST,
            CASE WHEN p_order = 'asc'                                     THEN f.location_of_property END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc'                                    THEN f.location_of_property END DESC NULLS LAST
        LIMIT p_limit OFFSET p_offset
    )
    SELECT json_build_object(
        'rows',  COALESCE(json_agg(paged), '[]'::json),
        'total', (SELECT total FROM counted)
    ) INTO result
    FROM paged;

    RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.get_bills_filtered(TEXT, TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT, INTEGER, INTEGER, TEXT, TEXT, INTEGER, INTEGER, TEXT, TEXT, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_bills_filtered(TEXT, TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT, INTEGER, INTEGER, TEXT, TEXT, INTEGER, INTEGER, TEXT, TEXT, INTEGER) TO authenticated;

-- 2. Scout-next RPC: same authenticated-session gate.
CREATE OR REPLACE FUNCTION public.android_get_next_scoutable_property(
    p_lat DOUBLE PRECISION,
    p_lng DOUBLE PRECISION,
    p_city TEXT DEFAULT '',
    p_list_id BIGINT DEFAULT NULL,
    p_q TEXT DEFAULT '',
    p_vpt INTEGER DEFAULT -1,
    p_condition_min DOUBLE PRECISION DEFAULT NULL,
    p_condition_max DOUBLE PRECISION DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result JSON;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'BARN scanner access requires an authenticated session'
            USING ERRCODE = '42501';
    END IF;

    WITH scoped AS (
        SELECT
            b.apn,
            b.location_of_property,
            b.city,
            b.has_vpt,
            b.condition_score,
            b.streetview_image_path,
            p.row_json,
            NULLIF(p.row_json->>'CENTROID_X', '')::DOUBLE PRECISION AS centroid_x,
            NULLIF(p.row_json->>'CENTROID_Y', '')::DOUBLE PRECISION AS centroid_y
        FROM public.bills b
        LEFT JOIN public.parcels p
            ON p."APN" = b.apn
        WHERE
            (p_q = '' OR p_q IS NULL OR b.location_of_property ILIKE '%' || p_q || '%' OR b.apn ILIKE '%' || p_q || '%')
            AND (p_city = '' OR p_city IS NULL OR LOWER(b.city) = LOWER(p_city))
            AND (p_vpt = -1 OR p_vpt IS NULL OR b.has_vpt = p_vpt)
            AND (p_condition_min IS NULL OR COALESCE(b.condition_score, -1) >= p_condition_min)
            AND (p_condition_max IS NULL OR COALESCE(b.condition_score, 999) <= p_condition_max)
            AND NOT EXISTS (
                SELECT 1
                FROM public.scout_results sr
                WHERE sr.apn = b.apn
            )
            AND (
                p_list_id IS NULL OR EXISTS (
                    SELECT 1
                    FROM public.list_properties lp
                    WHERE lp.list_id = p_list_id
                      AND lp.apn = b.apn
                )
            )
    ),
    with_coords AS (
        SELECT
            apn,
            location_of_property,
            city,
            has_vpt,
            condition_score,
            streetview_image_path,
            CASE
                WHEN centroid_x IS NULL OR centroid_y IS NULL OR centroid_x = 0 OR centroid_y = 0 THEN NULL
                ELSE (centroid_x / 20037508.34) * 180
            END AS longitude,
            CASE
                WHEN centroid_x IS NULL OR centroid_y IS NULL OR centroid_x = 0 OR centroid_y = 0 THEN NULL
                ELSE 180 / pi() * (
                    2 * atan(exp(((centroid_y / 20037508.34) * 180) * pi() / 180)) - pi() / 2
                )
            END AS latitude
        FROM scoped
    ),
    navigable AS (
        SELECT
            *,
            6371 * 2 * asin(
                sqrt(
                    power(sin(radians(latitude - p_lat) / 2), 2) +
                    cos(radians(p_lat)) * cos(radians(latitude)) *
                    power(sin(radians(longitude - p_lng) / 2), 2)
                )
            ) AS distance_km
        FROM with_coords
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ),
    ranked AS (
        SELECT *
        FROM navigable
        ORDER BY distance_km ASC, location_of_property ASC NULLS LAST
    ),
    nearest AS (
        SELECT *
        FROM ranked
        LIMIT 1
    ),
    remaining AS (
        SELECT GREATEST(COUNT(*) - 1, 0) AS remaining_count
        FROM navigable
    )
    SELECT json_build_object(
        'property',
        (
            SELECT CASE
                WHEN EXISTS (SELECT 1 FROM nearest) THEN json_build_object(
                    'apn', nearest.apn,
                    'address', nearest.location_of_property,
                    'city', nearest.city,
                    'latitude', nearest.latitude,
                    'longitude', nearest.longitude,
                    'has_vpt', (nearest.has_vpt = 1),
                    'condition_score', nearest.condition_score,
                    'streetview_image_path', nearest.streetview_image_path
                )
                ELSE NULL
            END
            FROM nearest
        ),
        'remaining',
        COALESCE((SELECT remaining_count FROM remaining), 0)
    ) INTO result;

    RETURN COALESCE(result, json_build_object('property', NULL, 'remaining', 0));
END;
$$;

REVOKE ALL ON FUNCTION public.android_get_next_scoutable_property(DOUBLE PRECISION, DOUBLE PRECISION, TEXT, BIGINT, TEXT, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.android_get_next_scoutable_property(DOUBLE PRECISION, DOUBLE PRECISION, TEXT, BIGINT, TEXT, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION) TO authenticated;

-- 3. Direct table access used by Android list/scout screens: any
-- authenticated user may access them.
GRANT SELECT ON public.bills TO authenticated;
GRANT SELECT ON public.parcels TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.lists TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.list_properties TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.scout_results TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

ALTER TABLE public.bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parcels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.list_properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scout_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read bills" ON public.bills;
DROP POLICY IF EXISTS "Admins can read bills" ON public.bills;
CREATE POLICY "Authenticated users can read bills"
ON public.bills
FOR SELECT
TO authenticated
USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Authenticated users can read parcels" ON public.parcels;
DROP POLICY IF EXISTS "Admins can read parcels" ON public.parcels;
CREATE POLICY "Authenticated users can read parcels"
ON public.parcels
FOR SELECT
TO authenticated
USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Authenticated users can manage lists" ON public.lists;
DROP POLICY IF EXISTS "Admins can manage lists" ON public.lists;
CREATE POLICY "Authenticated users can manage lists"
ON public.lists
FOR ALL
TO authenticated
USING (auth.uid() IS NOT NULL)
WITH CHECK (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Authenticated users can manage list properties" ON public.list_properties;
DROP POLICY IF EXISTS "Admins can manage list properties" ON public.list_properties;
CREATE POLICY "Authenticated users can manage list properties"
ON public.list_properties
FOR ALL
TO authenticated
USING (auth.uid() IS NOT NULL)
WITH CHECK (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Authenticated users can manage scout results" ON public.scout_results;
DROP POLICY IF EXISTS "Admins can manage scout results" ON public.scout_results;
CREATE POLICY "Authenticated users can manage scout results"
ON public.scout_results
FOR ALL
TO authenticated
USING (auth.uid() IS NOT NULL)
WITH CHECK (auth.uid() IS NOT NULL);
