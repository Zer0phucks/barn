# Android Supabase Scanner Phase 1 Design

**Date:** 2026-04-05
**Status:** Draft for review
**Scope:** `android/` Phase 1 architecture change

## Summary

The Android Scout app should stop depending on the Flask scanner app for day-to-day property browsing and scouting. Phase 1 moves the Android app to direct Supabase access for:

- property search, filtering, sorting, and pagination
- favorites
- lists and list membership
- map marker loading
- live scouting and scout result submission
- scouting statistics

Phase 1 explicitly does **not** move scanner worker controls into Android. Features such as scan start/stop/resume, discoveries acknowledgment, research/contact/condition/PG&E worker orchestration, and outreach job orchestration stay outside the Android app for now.

## Goals

- Use the same Supabase authentication model in Android that the BARN web app already uses.
- Remove Android reliance on the Flask scanner runtime for browsing and scouting.
- Preserve the same search, sort, and filter semantics as the scanner web app.
- Allow the Android UI to display a narrower mobile-friendly column set without reducing query power.
- Keep live scouting behavior functionally equivalent to the current web-backed flow.

## Non-Goals

- Rebuild the scanner worker control panel in Android.
- Preserve offline-first behavior for Phase 1.
- Refactor the Flask scanner web app away from its current routes.
- Move every scanner/admin feature into Android in one pass.

## User Experience

Android users will continue to log in with the same Supabase-backed credentials used by the BARN web app. After login, all property browsing and scouting actions will go directly to Supabase. The visible mobile UI may stay slimmer than the web scanner table, but users should still be able to search and sort and filter with the same effective power as the web scanner.

This phase is allowed to be online-only. If Supabase is unavailable or the network fails, Android should show explicit retryable errors rather than pretending the action succeeded locally.

## Architecture

### Current State

The Android app currently uses:

- `SupabaseAuthManager` for authentication
- Retrofit/Flask APIs in `ScoutApiService` for property, list, and scouting actions
- local Room tables for cached map data and unsynced scout results

This creates an architecture split where auth is Supabase-native, but core scanner usage still depends on the Flask app.

### Target State

Android becomes a first-class Supabase client for Phase 1 scanner functionality.

The new architecture should be:

- `SupabaseAuthManager` remains the source of auth state and JWT refresh
- Android repositories depend on a Supabase-backed scanner data client instead of `ScoutApiService`
- Supabase becomes the only backend dependency for browsing and scouting
- Flask remains in place for the web scanner and deferred worker-control features

## Component Design

### Android Data Layer

Replace the Retrofit-first scanner contract with a dedicated Supabase scanner client, for example:

- `SupabaseScannerService`
- `SupabaseScannerRepository`
- request/response DTOs that match the mobile Supabase contract

Responsibilities:

- execute authenticated RPC calls for property search and “next scoutable property”
- execute direct table operations or narrow RPCs for favorites, lists, list membership, and scout results
- normalize Supabase row shapes into Android models already used by the UI
- keep Android business logic thin and avoid duplicating scanner filtering logic in Kotlin

### Android Repositories

The existing repositories should be refactored so their source of truth is Supabase rather than Flask:

- `PropertyRepository`
  - load property pages from Supabase RPC
  - load filtered markers from Supabase
  - fetch next scoutable property from Supabase RPC
- `ListRepository`
  - list/create/delete lists
  - list detail reads
  - add/remove APNs from lists
- `ScoutRepository`
  - submit scout results directly to Supabase
  - load stats directly from Supabase

### Android UI

The existing screen structure can remain mostly intact:

- `PropertiesScreen`
- `ListsScreen`
- `ListDetailScreen`
- `MapScreen`
- `LiveScoutScreen`
- `StatsScreen`

The UI does not need to display every web column. It should display a mobile-focused subset while still offering the same practical query power.

## Supabase Contract

Phase 1 should expose a small, intentional Supabase surface for Android instead of having the app assemble complex raw queries ad hoc.

### Property Search RPC

Add or formalize a Supabase RPC for Android property search that preserves the web scanner semantics:

- search text
- city
- zip
- power
- VPT-only
- delinquent
- favorites-only
- condition
- out-of-state
- research status
- “new” discovery filter
- sort
- order
- page
- page size

Expected output should already include the fields Android needs for:

- table/list rows
- map markers
- navigation/scouting

Recommended output fields:

- `apn`
- `location_of_property`
- `city`
- `has_vpt`
- `delinquent`
- `power_status`
- `condition_score`
- `streetview_image_path`
- `research_status`
- `added_at`
- `row_json` or precomputed coordinates
- favorite flag

If practical, Android should use the same core RPC semantics already used by the web scanner rather than inventing slightly different filter behavior.

### Next Scoutable Property RPC

Add a dedicated RPC for “next property” selection. Android should not calculate this by downloading a large property set and filtering locally.

Inputs:

- current latitude/longitude
- optional city
- optional list id
- optional query
- VPT filter
- condition range if needed

Behavior:

- exclude already-scouted APNs
- exclude rows without usable coordinates
- apply the same filters used elsewhere
- return the nearest eligible property
- return remaining count

Output:

- property payload
- remaining count

### Table Access

Android Phase 1 may use direct access or narrow helper RPCs for:

- `lists`
- `list_properties`
- `favorites`
- `scout_results`

If direct table access is used, it must be protected by RLS and scoped to authenticated users as appropriate.

## Security and Access Model

Android should use the same authenticated Supabase user session as the web app. That means Phase 1 requires a mobile-safe Supabase access pattern rather than service-role style access.

This phase should include reviewing and tightening database access for Android:

- ensure authenticated users can read the scanner property/query surface needed by mobile
- ensure authenticated users can mutate only the list/favorite/scout tables they are supposed to use
- avoid exposing broad unsafe table access if an RPC/view is more appropriate

If existing scanner tables currently rely on disabled RLS or server-trusted access patterns, Phase 1 should introduce a mobile-safe access layer rather than reusing unsafe assumptions unchanged.

## Data Flow

### Login

1. Android signs in through Supabase auth.
2. `SupabaseAuthManager` stores access and refresh tokens.
3. All subsequent scanner requests use the Supabase JWT.
4. On 401-style failures, Android attempts token refresh and retries once.

### Property Browsing

1. User changes filters or paging in Android.
2. `PropertyRepository` calls the property search RPC.
3. Supabase returns paginated rows using web-equivalent filter/sort semantics.
4. Android renders a narrowed mobile row layout.

### Map Loading

1. Android requests filtered property data for the active filter set.
2. Returned rows are mapped to marker models.
3. Map displays only Supabase-backed results for the current query context.

### Lists and Favorites

1. Android reads and mutates lists/favorites directly in Supabase.
2. Property queries reflect list and favorite filters using Supabase state.

### Live Scouting

1. Android obtains current device location.
2. Android calls the “next scountable property” RPC with active filters.
3. Supabase returns the nearest eligible property and remaining count.
4. User navigates to the property and submits a scout result.
5. Android writes the result directly to `scout_results`.
6. Android only advances to the next property after Supabase confirms the write.

### Statistics

`StatsScreen` should read live scouting totals from Supabase rather than relying on locally cached or Flask-derived state.

## Error Handling

Android should treat Supabase as the single required backend for Phase 1.

Supported failure categories:

- auth expired
- permission denied
- connectivity failure
- malformed or incomplete data

Expected behavior:

- attempt token refresh on auth failure
- force re-login if refresh fails
- preserve the current search/filter state on failed reads
- keep scout mode active with explicit retry options on failed “next property” calls
- do not mark a scout submission complete until Supabase confirms success
- do not silently fall back to Flask

Because Phase 1 is online-only, Android should remove or stop using “saved locally, sync later” behavior for core scouting writes.

## Android Code Changes

Likely areas to modify:

- `android/app/src/main/java/com/vpt/scout/ScoutApiService.kt`
- `android/app/src/main/java/com/vpt/scout/Repositories.kt`
- `android/app/src/main/java/com/vpt/scout/ScoutApplication.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/PropertiesScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/MapScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/ListsScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt`
- `android/app/src/main/res/values/strings.xml`

Likely cleanup:

- remove `api_base_url` and `api_key` usage from Android Phase 1 scanner flows
- reduce reliance on Room for server-backed property/scouting state
- keep only local state that still serves a clear UI purpose

## Supabase / SQL Changes

Phase 1 will likely require one or more SQL changes:

- formalize or add a mobile-safe property search RPC
- add a mobile-safe “next scoutable property” RPC
- add or update RLS/policies/views needed for authenticated Android access
- possibly add helper views/functions for list detail or stats if direct table access is awkward

The intent is not to recreate the Flask API inside SQL one route at a time. The intent is to define a small stable contract that Android can depend on directly.

## Testing Strategy

### 1. Database Contract Verification

Verify the Supabase contract for:

- property filter parity with the web scanner
- sort parity with the web scanner
- favorites filtering
- list membership filtering
- “next property” selection
- already-scouted exclusion
- no-coordinate exclusion

### 2. Android Repository Tests

Add or update tests for:

- property search parameter mapping
- paging and sort mapping
- list CRUD
- add/remove properties from lists
- favorite toggling
- scout result submission success/failure behavior
- token refresh and retry behavior

### 3. Android Screen Tests

Focus on high-value interaction behavior:

- filters persist across retries
- list detail loads from Supabase
- map refresh respects active filters
- live scout mode handles no-results and no-coordinate cases
- stats reflect live Supabase data

## Rollout

Phase 1 should be a clean Android cutover:

- Android browsing and scouting use Supabase directly
- Android no longer depends on Flask scanner endpoints for those features
- the Flask/web scanner remains unchanged for web usage and deferred worker controls

This keeps the migration bounded while still achieving the main architectural goal: Android no longer depends on the scan app runtime for core usage.

## Deferred Work

The following remain explicitly deferred:

- scan start/stop/resume from Android
- worker status and discoveries management in Android
- research/contact/condition/PG&E worker controls in Android
- outreach scoring, pitch generation, and send orchestration in Android
- offline-first scouting sync

## Acceptance Criteria

Phase 1 is complete when:

1. Android signs in with the same Supabase auth flow as the web app.
2. Android property browsing no longer depends on Flask endpoints.
3. Android supports the same effective search/filter/sort behavior as the web scanner.
4. Android favorites and lists read/write directly through Supabase.
5. Android map data is loaded directly from Supabase for the active filters.
6. Android live scouting fetches the next property directly from Supabase.
7. Android scout result submission writes directly to Supabase and only advances after confirmed success.
8. Android no longer requires `api_base_url` or `api_key` for Phase 1 scanner features.
