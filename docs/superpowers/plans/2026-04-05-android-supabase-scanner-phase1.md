# Android Supabase Scanner Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Android property browsing and scouting off the Flask scanner runtime and onto direct Supabase access while preserving the web scanner’s filter/sort behavior.

**Architecture:** Add a dedicated Supabase-backed Android scanner client that uses the existing Supabase auth session and JWT refresh flow. Use SQL/RPC as the stable contract for property search and “next scoutable property,” then refactor Android repositories and screens to use that contract directly. Keep worker-control features out of scope and do not preserve offline-sync behavior in this phase.

**Tech Stack:** Kotlin, Jetpack Compose, OkHttp, Gson, Supabase Auth REST, Supabase PostgREST/RPC, existing Android JVM tests, scanner SQL migrations

---

## File Structure

### Create

- `scan/db_migrations/supa_migration_android_scanner_phase1.sql`
  Purpose: Add or formalize the mobile-safe Supabase contract for Android browsing and scouting. Include any new RPCs/views and any RLS/policy changes required for authenticated mobile access.

- `android/app/src/main/java/com/vpt/scout/ScannerModels.kt`
  Purpose: Hold shared scanner DTOs and request/response models currently mixed into `ScoutApiService.kt`, so the Android UI and repositories can use the same models without depending on Retrofit.

- `android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt`
  Purpose: Direct Supabase REST/RPC client for Android. Own authenticated HTTP calls, JSON parsing, and model mapping for scanner features.

- `android/app/src/test/java/com/vpt/scout/SupabaseScannerServiceTest.kt`
  Purpose: Verify request encoding, auth headers, response parsing, and next-property behavior for the new Supabase client.

- `android/app/src/test/java/com/vpt/scout/SupabaseRepositoryTest.kt`
  Purpose: Verify repository behavior against a fake service, especially online-only submission and filter preservation.

### Modify

- `android/app/build.gradle.kts`
  Purpose: Add any test-only dependencies needed for HTTP contract tests, such as `mockwebserver`.

- `android/app/src/main/java/com/vpt/scout/ScoutApiService.kt`
  Purpose: Remove Retrofit ownership from active scanner paths. Either delete the Retrofit interface after extraction or reduce it to a legacy compatibility shim if needed during the cutover.

- `android/app/src/main/java/com/vpt/scout/Repositories.kt`
  Purpose: Switch `PropertyRepository`, `ListRepository`, and `ScoutRepository` to the new Supabase client and remove local-first sync assumptions from Phase 1 flows.

- `android/app/src/main/java/com/vpt/scout/ScoutApplication.kt`
  Purpose: Wire the app container to `SupabaseScannerService` and stop constructing repositories around the Retrofit API.

- `android/app/src/main/java/com/vpt/scout/SupabaseAuthManager.kt`
  Purpose: Expose the Supabase base URL and anon key in a controlled way for the direct REST/RPC client, while keeping token refresh behavior centralized.

- `android/app/src/main/java/com/vpt/scout/MainActivity.kt`
  Purpose: Update screen wiring if any repository signatures change, especially if `CollectionRepository` is no longer needed for the map flow.

- `android/app/src/main/java/com/vpt/scout/ui/screens/PropertiesScreen.kt`
  Purpose: Keep the current screen shape, but source property pages, list actions, and select-all behavior directly from Supabase-backed repositories.

- `android/app/src/main/java/com/vpt/scout/ui/screens/MapScreen.kt`
  Purpose: Stop relying on cached Room markers as the primary source of truth; load active markers directly from the repository’s Supabase-backed query path.

- `android/app/src/main/java/com/vpt/scout/ui/screens/ListsScreen.kt`
  Purpose: Keep list CRUD and detail flows working against direct Supabase data.

- `android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt`
  Purpose: Use the Supabase-backed “next scoutable property” call and enforce confirmed-write-before-advance behavior.

- `android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt`
  Purpose: Remove pending-sync assumptions and show live Supabase scouting stats only.

- `android/app/src/main/res/values/strings.xml`
  Purpose: Remove `api_base_url` / `api_key` as required scanner configuration for Phase 1 and keep only Supabase-backed config in active use.

### Leave In Place Unless Cleanup Is Safe

- `android/app/src/main/java/com/vpt/scout/ScoutDatabase.kt`
- `android/app/src/main/java/com/vpt/scout/data/local/Entities.kt`
- `android/app/src/main/java/com/vpt/scout/data/local/Daos.kt`

These files currently support local caching and sync. Do not delete them in the first repository-cutover task. Once the app compiles and the Supabase-backed flows are working, remove or trim them only if they are truly unused by Phase 1.

## Task 1: Extract Shared Scanner Models and Add a Testable Supabase Client Skeleton

**Files:**
- Create: `android/app/src/main/java/com/vpt/scout/ScannerModels.kt`
- Create: `android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt`
- Create: `android/app/src/test/java/com/vpt/scout/SupabaseScannerServiceTest.kt`
- Modify: `android/app/build.gradle.kts`
- Modify: `android/app/src/main/java/com/vpt/scout/ScoutApiService.kt`

- [ ] **Step 1: Add a failing HTTP contract test for Supabase RPC and table requests**

```kotlin
@Test
fun `getProperties posts scanner filters to get_bills_filtered rpc`() {
    val server = MockWebServer()
    server.enqueueJson("""{"rows":[],"total":0}""")

    val service = SupabaseScannerService(
        baseUrl = server.url("/").toString(),
        anonKey = "anon-key",
        accessTokenProvider = { "jwt-token" },
        authManager = null
    )

    runBlocking {
        service.getProperties(
            filters = PropertyFilters(city = "OAKLAND", query = "elm", vptOnly = true, scouted = false, listId = 7L),
            page = 1,
            perPage = 50
        )
    }

    val request = server.takeRequest()
    assertEquals("/rest/v1/rpc/get_bills_filtered", request.path)
    assertEquals("Bearer jwt-token", request.getHeader("Authorization"))
    assertEquals("anon-key", request.getHeader("apikey"))
    assertTrue(request.body.readUtf8().contains("\"p_city\":\"OAKLAND\""))
}
```

- [ ] **Step 2: Run the new service test to verify it fails**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseScannerServiceTest"`

Expected: FAIL because `SupabaseScannerService` and the request behavior do not exist yet.

- [ ] **Step 3: Extract scanner DTOs into a shared model file**

```kotlin
data class Property(
    val apn: String,
    val address: String?,
    val city: String?,
    val latitude: Double?,
    val longitude: Double?,
    val hasVpt: Boolean = false,
    val conditionScore: Float?,
    val isScouted: Boolean = false,
    val streetviewImagePath: String?
)

data class PropertiesResponse(
    val properties: List<Property>,
    val total: Int,
    val page: Int,
    val perPage: Int,
    val totalPages: Int
)
```

- [ ] **Step 4: Implement the first version of `SupabaseScannerService`**

```kotlin
class SupabaseScannerService(
    private val baseUrl: String,
    private val anonKey: String,
    private val accessTokenProvider: () -> String?,
    private val authManager: SupabaseAuthManager? = null,
    private val client: OkHttpClient = buildClient(accessTokenProvider, authManager)
) {
    suspend fun getProperties(
        filters: PropertyFilters,
        page: Int,
        perPage: Int
    ): PropertiesResponse {
        val body = JSONObject()
            .put("p_q", filters.query.orEmpty())
            .put("p_city", filters.city.orEmpty())
            .put("p_vpt", if (filters.vptOnly) 1 else 0)
            .put("p_limit", perPage)
            .put("p_offset", (page - 1) * perPage)

        val request = Request.Builder()
            .url("$baseUrl/rest/v1/rpc/get_bills_filtered")
            .addHeader("apikey", anonKey)
            .addHeader("Authorization", "Bearer ${accessTokenProvider().orEmpty()}")
            .post(body.toString().toRequestBody(JSON))
            .build()

        return executePropertiesRequest(request)
    }
}
```

- [ ] **Step 5: Add `MockWebServer` as a test dependency if the test needs it**

```kotlin
testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
```

- [ ] **Step 6: Run the service test to verify it passes**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseScannerServiceTest"`

Expected: PASS with the new client correctly encoding Supabase requests and headers.

- [ ] **Step 7: Commit the client skeleton**

```bash
git add android/app/build.gradle.kts \
  android/app/src/main/java/com/vpt/scout/ScannerModels.kt \
  android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt \
  android/app/src/main/java/com/vpt/scout/ScoutApiService.kt \
  android/app/src/test/java/com/vpt/scout/SupabaseScannerServiceTest.kt
git commit -m "feat: add supabase scanner client skeleton for android"
```

## Task 2: Add the Mobile-Safe Supabase SQL Contract

**Files:**
- Create: `scan/db_migrations/supa_migration_android_scanner_phase1.sql`
- Modify: `android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt`
- Test: `android/app/src/test/java/com/vpt/scout/SupabaseScannerServiceTest.kt`

- [ ] **Step 1: Add a failing test for the next-property RPC path and parsed response**

```kotlin
@Test
fun `getNextProperty calls next scoutable property rpc and parses the payload`() = runBlocking {
    server.enqueueJson(
        """
        {"property":{"apn":"1","address":"123 Test St","city":"OAKLAND","latitude":37.8,"longitude":-122.2},"remaining":4}
        """.trimIndent()
    )

    val response = service.getNextProperty(
        latitude = 37.8,
        longitude = -122.2,
        city = "OAKLAND",
        vptOnly = true,
        listId = 7L
    )

    assertEquals("1", response.property?.apn)
    assertEquals(4, response.remaining)
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseScannerServiceTest.getNextProperty*"`

Expected: FAIL because the dedicated next-property RPC path does not exist in the client yet.

- [ ] **Step 3: Write the Supabase migration for authenticated Android access**

```sql
create or replace function public.android_get_next_scoutable_property(
    p_lat double precision,
    p_lng double precision,
    p_city text default '',
    p_list_id bigint default null,
    p_q text default '',
    p_vpt integer default 0
) returns json
language plpgsql
security definer
as $$
declare
    result json;
begin
    -- Reuse the same bill/filter semantics as get_bills_filtered,
    -- then exclude already-scouted APNs and rows without coordinates.
    -- Return one nearest property plus the remaining count.
    return result;
end;
$$;
```

- [ ] **Step 4: Expand the migration to cover any required read/write policies**

```sql
-- Example shape only; adapt to the actual auth model used by BARN admin users.
alter table public.favorites enable row level security;
alter table public.lists enable row level security;
alter table public.list_properties enable row level security;
alter table public.scout_results enable row level security;

create policy "authenticated scanner reads"
on public.scout_results
for select
to authenticated
using (true);
```

- [ ] **Step 5: Finish the client methods against the new SQL contract**

```kotlin
suspend fun getNextProperty(
    latitude: Double,
    longitude: Double,
    city: String?,
    vptOnly: Boolean,
    listId: Long?
): NextPropertyResponse {
    val body = JSONObject()
        .put("p_lat", latitude)
        .put("p_lng", longitude)
        .put("p_city", city.orEmpty())
        .put("p_list_id", listId)
        .put("p_vpt", if (vptOnly) 1 else 0)

    return executeNextPropertyRequest(
        rpc = "android_get_next_scoutable_property",
        body = body
    )
}
```

- [ ] **Step 6: Apply the migration to the Supabase project**

Run in Supabase SQL Editor: contents of `scan/db_migrations/supa_migration_android_scanner_phase1.sql`

Expected: The migration runs without SQL errors and exposes the Android Phase 1 RPC/policy contract.

- [ ] **Step 7: Re-run the service tests**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseScannerServiceTest"`

Expected: PASS with both property-search and next-property client paths green.

- [ ] **Step 8: Commit the SQL contract**

```bash
git add scan/db_migrations/supa_migration_android_scanner_phase1.sql \
  android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt \
  android/app/src/test/java/com/vpt/scout/SupabaseScannerServiceTest.kt
git commit -m "feat: add supabase contract for android scanner phase 1"
```

## Task 3: Refactor Repositories and App Wiring to Use the Supabase Client

**Files:**
- Modify: `android/app/src/main/java/com/vpt/scout/Repositories.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ScoutApplication.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/SupabaseAuthManager.kt`
- Create: `android/app/src/test/java/com/vpt/scout/SupabaseRepositoryTest.kt`

- [ ] **Step 1: Add a failing repository test for online-only scout submission**

```kotlin
@Test
fun `submitScoutResult does not report success unless supabase write succeeds`() = runBlocking {
    val service = FakeSupabaseScannerService(submitScoutResultError = IOException("offline"))
    val repository = ScoutRepository(service)

    val result = runCatching {
        repository.submitScoutResult("1", followUp = true, flyered = false, notes = null, latitude = 1.0, longitude = 2.0)
    }

    assertTrue(result.isFailure)
}
```

- [ ] **Step 2: Run the repository test to verify it fails**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseRepositoryTest"`

Expected: FAIL because the repositories still assume Retrofit plus local-sync behavior.

- [ ] **Step 3: Rewrite the repositories around `SupabaseScannerService`**

```kotlin
class ScoutRepository(
    private val scannerService: SupabaseScannerService
) {
    suspend fun submitScoutResult(
        apn: String,
        followUp: Boolean,
        flyered: Boolean,
        notes: String?,
        latitude: Double?,
        longitude: Double?
    ): Long {
        return scannerService.submitScoutResult(
            ScoutResultRequest(apn, followUp, flyered, notes, latitude, longitude)
        )
    }

    suspend fun getStats(): ScoutStats = scannerService.getScoutStats()
}
```

- [ ] **Step 4: Update the app container to construct the new client**

```kotlin
// In SupabaseAuthManager.kt
val projectUrl: String get() = supabaseUrl
val anonKey: String get() = supabaseAnonKey

// In ScoutApplication.kt
val scannerService: SupabaseScannerService by lazy {
    SupabaseScannerService(
        baseUrl = authManager.projectUrl,
        anonKey = authManager.anonKey,
        accessTokenProvider = { authManager.getAccessToken() },
        authManager = authManager
    )
}

val propertyRepository by lazy { PropertyRepository(scannerService) }
val listRepository by lazy { ListRepository(scannerService) }
val scoutRepository by lazy { ScoutRepository(scannerService) }
```

- [ ] **Step 5: Keep Room types in place until the app compiles**

Do not delete `ScoutDatabase`, `PropertyDao`, `CollectionDao`, or `ScoutResultDao` in this task. First get all active repositories switched over and tested. Clean up dead local-sync code only after the new wiring is stable.

- [ ] **Step 6: Re-run repository tests**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.SupabaseRepositoryTest"`

Expected: PASS with repositories now delegating to Supabase and failing fast on write errors.

- [ ] **Step 7: Commit the repository refactor**

```bash
git add android/app/src/main/java/com/vpt/scout/Repositories.kt \
  android/app/src/main/java/com/vpt/scout/ScoutApplication.kt \
  android/app/src/main/java/com/vpt/scout/SupabaseAuthManager.kt \
  android/app/src/test/java/com/vpt/scout/SupabaseRepositoryTest.kt
git commit -m "refactor: move android scanner repositories to supabase"
```

## Task 4: Cut the Compose Screens Over to the Supabase-Backed Repositories

**Files:**
- Modify: `android/app/src/main/java/com/vpt/scout/MainActivity.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/PropertiesScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/MapScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/ListsScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt`
- Test: `android/app/src/test/java/com/vpt/scout/ui/screens/ScoutNextPropertyResolverTest.kt`

- [ ] **Step 1: Add or update a failing test for scout-mode “do not advance on failed submit” behavior**

```kotlin
@Test
fun `failed scout submission leaves the user on the questionnaire step`() {
    val nextState = reduceSubmissionResult(
        current = ScoutState.SUBMITTING,
        submissionSucceeded = false
    )

    assertEquals(ScoutState.QUESTIONNAIRE, nextState)
}
```

- [ ] **Step 2: Run the relevant screen helper tests to verify failure**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.ui.screens.*"`

Expected: FAIL once the new online-only behavior is asserted and the helper/reducer does not exist yet.

- [ ] **Step 3: Update `PropertiesScreen` and `MapScreen` to query Supabase-backed repositories directly**

```kotlin
LaunchedEffect(selectedCity, vptOnly, showUnscoutedOnly, selectedListId) {
    loadProperties(page = 1)
}

LaunchedEffect(activeFilters) {
    markers = propertyRepository.loadMarkers(activeFilters)
}
```

- [ ] **Step 4: Update `LiveScoutScreen` to use the Supabase next-property call and confirmed-write flow**

```kotlin
try {
    scoutRepository.submitScoutResult(...)
    scoutedCount++
    findNextProperty()
} catch (e: Exception) {
    error = e.message ?: "Failed to submit"
    scoutState = ScoutState.QUESTIONNAIRE
}
```

- [ ] **Step 5: Remove Phase 1 UI that implies local sync**

```kotlin
// Delete the sync button from StatsScreen.
// Do not call syncPendingResults() in any Phase 1 screen.
```

- [ ] **Step 6: Update `MainActivity` if `CollectionRepository` is no longer needed**

```kotlin
MapScreen(
    propertyRepository = container.propertyRepository,
    listRepository = container.listRepository
)
```

- [ ] **Step 7: Re-run the screen helper tests**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.ui.screens.*"`

Expected: PASS with scout-mode resolver logic and list-selection helpers still green after the cutover.

- [ ] **Step 8: Commit the screen cutover**

```bash
git add android/app/src/main/java/com/vpt/scout/MainActivity.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/PropertiesScreen.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/MapScreen.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/ListsScreen.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt \
  android/app/src/test/java/com/vpt/scout/ui/screens/ScoutNextPropertyResolverTest.kt
git commit -m "feat: switch android scanner screens to supabase"
```

## Task 5: Remove Active Flask Config Dependence and Clean Up Legacy Paths

**Files:**
- Modify: `android/app/src/main/res/values/strings.xml`
- Modify: `android/app/src/main/java/com/vpt/scout/ScoutApiService.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ScoutDatabase.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/data/local/Daos.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/data/local/Entities.kt`
- Test: `android/app/src/test/java/com/vpt/scout/FilteredMapPropertiesTest.kt`

- [ ] **Step 1: Add a failing test or assertion for the new direct-marker path**

```kotlin
@Test
fun `marker loading no longer depends on cached property entities`() {
    val service = FakeSupabaseScannerService(markers = listOf(Property("1", "A", "OAKLAND", 37.8, -122.2, false, null, false, null)))
    val repository = PropertyRepository(service)

    val markers = runBlocking { repository.loadMarkers(PropertyFilters(city = "OAKLAND")) }

    assertEquals(listOf("1"), markers.map { it.apn })
}
```

- [ ] **Step 2: Run the cleanup-related tests to verify failure**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.FilteredMapPropertiesTest"`

Expected: FAIL because the repository still routes map behavior through Room-only helpers.

- [ ] **Step 3: Remove active `api_base_url` / `api_key` dependence from Android**

```xml
<!-- Delete these once no active code reads them -->
<!-- <string name="api_base_url">https://app.bayrenewal.org</string> -->
<!-- <string name="api_key">P@ssw0rdz</string> -->
```

- [ ] **Step 4: Delete or trim dead Retrofit/Room-only code only after call sites are gone**

```kotlin
// Example end state: keep Room only if another screen still reads it.
// Otherwise, remove DAO/entity methods that exist solely for old Flask sync flows.
```

- [ ] **Step 5: Re-run the targeted cleanup test and then the full Android unit suite**

Run: `cd android && ./gradlew test --tests "com.vpt.scout.FilteredMapPropertiesTest"`

Expected: PASS with marker loading coming from the Supabase-backed repository path.

Run: `cd android && ./gradlew test`

Expected: PASS for the full JVM unit suite.

- [ ] **Step 6: Commit the cleanup**

```bash
git add android/app/src/main/res/values/strings.xml \
  android/app/src/main/java/com/vpt/scout/ScoutApiService.kt \
  android/app/src/main/java/com/vpt/scout/ScoutDatabase.kt \
  android/app/src/main/java/com/vpt/scout/data/local/Daos.kt \
  android/app/src/main/java/com/vpt/scout/data/local/Entities.kt \
  android/app/src/test/java/com/vpt/scout/FilteredMapPropertiesTest.kt
git commit -m "chore: remove legacy flask config from android scanner"
```

## Final Verification Checklist

- [ ] Run: `cd android && ./gradlew test`
  Expected: PASS

- [ ] Manual Android smoke test:
  - log in with Supabase credentials
  - load properties with city/search/VPT filters
  - open list detail and remove an item
  - open map and confirm markers load
  - run live scout mode and verify failed submit does not advance
  - verify stats load without a sync button

- [ ] Manual Supabase smoke test:
  - property search RPC returns filtered rows
  - next scoutable property RPC excludes already-scouted APNs
  - authenticated users can read/write the intended tables only

- [ ] Update the Phase 1 spec if implementation constraints changed materially during the work.
