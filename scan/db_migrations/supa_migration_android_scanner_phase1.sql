-- Android scanner Phase 1 support.
-- Adds a mobile-friendly RPC for "next scoutable property" so the Android app
-- can talk directly to Supabase instead of depending on the Flask runtime.

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
AS $$
DECLARE
    result JSON;
BEGIN
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
