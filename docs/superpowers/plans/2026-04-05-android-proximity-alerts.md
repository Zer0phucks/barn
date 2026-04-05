# Android Proximity Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add background proximity alerts that notify the user when they are near the closest unscouted property and open an in-app single-property scout session when tapped.

**Architecture:** Build a foreground location-monitoring service backed by the existing Supabase scanner client and a small proximity package for alert preferences, threshold/duplicate suppression, and notification routing. Reuse the existing nearest-unscouted RPC path for eligibility, then add a dedicated alerted-property scout screen so the user can navigate and still record the scout result against the exact APN.

**Tech Stack:** Kotlin, Jetpack Compose, Android foreground services, Fused Location Provider, NotificationCompat, DataStore Preferences, existing Supabase REST/RPC client, JVM unit tests, Android debug APK verification

---

## File Structure

### Create

- `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertModels.kt`
  Purpose: Define proximity settings, alert session payloads, and suppression-state models without bloating `ScannerModels.kt`.

- `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertPreferences.kt`
  Purpose: Persist monitoring enabled state, threshold selection, and last-alert suppression metadata using DataStore.

- `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertCoordinator.kt`
  Purpose: Hold pure Kotlin decision logic for “nearest eligible property within threshold?” and duplicate suppression. This is the testable core used by the service.

- `android/app/src/main/java/com/vpt/scout/proximity/ProximityNotificationManager.kt`
  Purpose: Create the persistent monitoring notification and the proximity alert notification that opens the app into a single-property scout session.

- `android/app/src/main/java/com/vpt/scout/proximity/ProximityMonitorService.kt`
  Purpose: Run as the foreground service, request location updates, call the repository, invoke the coordinator, and post notifications.

- `android/app/src/main/java/com/vpt/scout/ui/screens/AlertedPropertyScoutScreen.kt`
  Purpose: Dedicated single-property scout session opened from a notification tap, including property summary, `Navigate`, and scout-result submission.

- `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertCoordinatorTest.kt`
  Purpose: Verify threshold entry, closest-only behavior, exit-radius suppression, and stop-alerting-on-scouted logic without Android framework dependencies.

- `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt`
  Purpose: Verify repository behavior for nearest-property lookup, alert-session hydration, and scouted-property exclusion.

- `android/app/src/test/java/com/vpt/scout/proximity/ProximityNotificationManagerTest.kt`
  Purpose: Verify notification intent payloads and action wiring at the JVM level where practical.

### Modify

- `android/app/src/main/AndroidManifest.xml`
  Purpose: Add background location, notification, and foreground-service permissions plus the service declaration and any intent metadata needed for notification routing.

- `android/app/build.gradle.kts`
  Purpose: Add any AndroidX/core test support needed for notifications or DataStore-backed preferences tests.

- `android/app/src/main/java/com/vpt/scout/ScoutApplication.kt`
  Purpose: Register singleton proximity dependencies and expose them through the app container.

- `android/app/src/main/java/com/vpt/scout/Repositories.kt`
  Purpose: Add repository entry points for nearest-unscouted lookup, exact APN hydration for alerted sessions, and reuse of scout-result submission in the new screen.

- `android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt`
  Purpose: Add any narrow helper needed for exact APN hydration if the alert session cannot fully rely on cached/notification payload data.

- `android/app/src/main/java/com/vpt/scout/MainActivity.kt`
  Purpose: Add notification/background-location permission handling and route notification taps into the new alerted-property scout screen.

- `android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt`
  Purpose: Extract any reusable scout-result form pieces so the alerted-property session does not duplicate complex form logic.

- `android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt`
  Purpose: Add a simple `Proximity Alerts` control card with enable/disable, threshold selection, and monitoring status.

### Leave In Place Unless Cleanup Is Safe

- `android/app/src/main/java/com/vpt/scout/ui/screens/MapScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ui/screens/PropertiesScreen.kt`
- `android/app/src/main/java/com/vpt/scout/ScannerModels.kt`

These files should not be expanded with background-alert logic beyond small reuse hooks. Keep proximity behavior concentrated in the new proximity package and the dedicated alert-session screen.

## Task 1: Add Pure Proximity Domain Logic and Preferences

**Files:**
- Create: `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertModels.kt`
- Create: `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertPreferences.kt`
- Create: `android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertCoordinator.kt`
- Create: `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertCoordinatorTest.kt`
- Modify: `android/app/build.gradle.kts`

- [ ] **Step 1: Write a failing coordinator test for threshold entry and duplicate suppression**

```kotlin
@Test
fun `returns an alert when nearest property enters threshold and was not previously alerted`() {
    val result = coordinator.evaluate(
        nearest = AlertCandidate(apn = "001", distanceFeet = 420f, isScouted = false),
        settings = ProximityAlertSettings(enabled = true, thresholdFeet = 500),
        suppression = AlertSuppressionState(lastAlertedApn = null, lastInsideThreshold = false)
    )

    assertEquals("001", result.alertApn)
    assertTrue(result.shouldNotify)
}
```

- [ ] **Step 2: Run the coordinator test to verify it fails**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertCoordinatorTest"`

Expected: FAIL because the proximity models and coordinator do not exist yet.

- [ ] **Step 3: Add focused proximity models**

```kotlin
data class ProximityAlertSettings(
    val enabled: Boolean = false,
    val thresholdFeet: Int = 500
)

data class AlertSuppressionState(
    val lastAlertedApn: String? = null,
    val lastInsideThreshold: Boolean = false
)

data class AlertCandidate(
    val apn: String,
    val distanceFeet: Float,
    val isScouted: Boolean
)
```

- [ ] **Step 4: Implement the minimal coordinator**

```kotlin
class ProximityAlertCoordinator {
    fun evaluate(
        nearest: AlertCandidate?,
        settings: ProximityAlertSettings,
        suppression: AlertSuppressionState
    ): EvaluationResult {
        if (!settings.enabled || nearest == null || nearest.isScouted) {
            return EvaluationResult.noAlert(suppression.copy(lastInsideThreshold = false))
        }
        val inside = nearest.distanceFeet <= settings.thresholdFeet
        val alreadyAlerted = suppression.lastAlertedApn == nearest.apn && suppression.lastInsideThreshold
        return if (inside && !alreadyAlerted) {
            EvaluationResult.alert(
                alertApn = nearest.apn,
                nextSuppression = AlertSuppressionState(nearest.apn, true)
            )
        } else {
            EvaluationResult.noAlert(
                suppression.copy(lastInsideThreshold = inside, lastAlertedApn = if (inside) nearest.apn else suppression.lastAlertedApn)
            )
        }
    }
}
```

- [ ] **Step 5: Add DataStore-backed preferences for settings and suppression state**

```kotlin
class ProximityAlertPreferences(private val context: Context) {
    val settings: Flow<ProximityAlertSettings> = context.dataStore.data.map { prefs -> ... }
    suspend fun setEnabled(enabled: Boolean) { ... }
    suspend fun setThresholdFeet(feet: Int) { ... }
    suspend fun updateSuppression(state: AlertSuppressionState) { ... }
}
```

- [ ] **Step 6: Re-run the coordinator test and add one more passing test for “closest already alerted does not notify again”**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertCoordinatorTest"`

Expected: PASS.

- [ ] **Step 7: Commit the proximity core**

```bash
git add android/app/build.gradle.kts \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertModels.kt \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertPreferences.kt \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityAlertCoordinator.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertCoordinatorTest.kt
git commit -m "feat: add proximity alert core logic"
```

## Task 2: Add Repository Support for Nearest Unscouted Alerts and Alert Session Hydration

**Files:**
- Modify: `android/app/src/main/java/com/vpt/scout/Repositories.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt`
- Create: `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt`

- [ ] **Step 1: Write a failing repository test for nearest unscouted lookup**

```kotlin
@Test
fun `getNearestUnscoutedProperty uses next-property rpc with global filters`() = runBlocking {
    val repository = ProximityAlertRepository(
        propertyRepository = propertyRepository,
        scoutRepository = scoutRepository
    )

    val property = repository.getNearestUnscoutedProperty(37.8, -122.2)

    assertEquals("001-100-100", property?.apn)
}
```

- [ ] **Step 2: Run the repository test to verify it fails**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertRepositoryTest"`

Expected: FAIL because the proximity repository does not exist yet.

- [ ] **Step 3: Add a narrow repository that reuses the existing nearest-unscouted RPC**

```kotlin
class ProximityAlertRepository(
    private val propertyRepository: PropertyRepository
) {
    suspend fun getNearestUnscoutedProperty(latitude: Double, longitude: Double): Property? {
        return propertyRepository.getNextProperty(
            latitude = latitude,
            longitude = longitude,
            city = null,
            vptOnly = false,
            listId = null
        ).property
    }
}
```

- [ ] **Step 4: Add an exact APN hydration path for the alerted-property session**

```kotlin
suspend fun getPropertyForAlert(apn: String): Property? {
    return propertyRepository.getPropertyByApn(apn)
}
```

- [ ] **Step 5: Extend `PropertyRepository` and, only if needed, `SupabaseScannerService`**

```kotlin
suspend fun getPropertyByApn(apn: String): Property? {
    return loadProperties(query = apn, perPage = 1).properties.firstOrNull { it.apn == apn }
}
```

- [ ] **Step 6: Re-run the repository test and add one more test for “returns null when property is already scouted”**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertRepositoryTest"`

Expected: PASS.

- [ ] **Step 7: Commit repository support**

```bash
git add android/app/src/main/java/com/vpt/scout/Repositories.kt \
  android/app/src/main/java/com/vpt/scout/SupabaseScannerService.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt
git commit -m "feat: add repository support for proximity alerts"
```

## Task 3: Add Notifications and the Foreground Monitoring Service

**Files:**
- Create: `android/app/src/main/java/com/vpt/scout/proximity/ProximityNotificationManager.kt`
- Create: `android/app/src/main/java/com/vpt/scout/proximity/ProximityMonitorService.kt`
- Create: `android/app/src/test/java/com/vpt/scout/proximity/ProximityNotificationManagerTest.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/main/java/com/vpt/scout/ScoutApplication.kt`

- [ ] **Step 1: Write a failing notification test for the alert tap intent**

```kotlin
@Test
fun `alert notification opens alerted scout route with apn`() {
    val pendingIntent = manager.buildAlertPendingIntent(apn = "001-100-100")
    val intent = shadowOf(pendingIntent).savedIntent

    assertEquals("alerted-scout/001-100-100", intent.getStringExtra("route"))
}
```

- [ ] **Step 2: Run the notification test to verify it fails**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityNotificationManagerTest"`

Expected: FAIL because the notification manager does not exist yet.

- [ ] **Step 3: Implement the notification manager with persistent and alert channels**

```kotlin
class ProximityNotificationManager(
    private val context: Context
) {
    fun showMonitoringNotification() { ... }
    fun showPropertyAlert(property: Property) { ... }
}
```

- [ ] **Step 4: Implement the foreground service with fused location updates**

```kotlin
class ProximityMonitorService : LifecycleService() {
    override fun onCreate() {
        startForeground(NOTIFICATION_ID, notificationManager.buildMonitoringNotification())
        requestLocationUpdates()
    }
}
```

- [ ] **Step 5: Register permissions and the service in the manifest**

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />

<service
    android:name=".proximity.ProximityMonitorService"
    android:foregroundServiceType="location"
    android:exported="false" />
```

- [ ] **Step 6: Re-run the notification test and build the app**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityNotificationManagerTest" && ./gradlew assembleDebug`

Expected: PASS, with the service compiling and the app building.

- [ ] **Step 7: Commit the monitoring service**

```bash
git add android/app/src/main/AndroidManifest.xml \
  android/app/src/main/java/com/vpt/scout/ScoutApplication.kt \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityNotificationManager.kt \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityMonitorService.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityNotificationManagerTest.kt
git commit -m "feat: add proximity monitoring service"
```

## Task 4: Add the Alerted-Property Scout Session and Navigation Routing

**Files:**
- Create: `android/app/src/main/java/com/vpt/scout/ui/screens/AlertedPropertyScoutScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/MainActivity.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt`
- Test: `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt`

- [ ] **Step 1: Write a failing session-flow test for loading a single alerted property**

```kotlin
@Test
fun `getPropertyForAlert returns exact alerted property by apn`() = runBlocking {
    val property = repository.getPropertyForAlert("001-100-100")
    assertEquals("001-100-100", property?.apn)
}
```

- [ ] **Step 2: Run the test to verify it fails for the new screen flow**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertRepositoryTest.getPropertyForAlert*"`

Expected: FAIL until the alert session path is wired end to end.

- [ ] **Step 3: Add a dedicated `alerted-scout/{apn}` route in `MainActivity.kt`**

```kotlin
composable(
    route = "alerted-scout/{apn}",
    arguments = listOf(navArgument("apn") { type = NavType.StringType })
) { backStackEntry ->
    AlertedPropertyScoutScreen(
        apn = backStackEntry.arguments?.getString("apn") ?: return@composable,
        proximityRepository = container.proximityAlertRepository,
        scoutRepository = container.scoutRepository,
        onBack = { navController.popBackStack() }
    )
}
```

- [ ] **Step 4: Implement the dedicated alert session screen**

```kotlin
@Composable
fun AlertedPropertyScoutScreen(...) {
    // load one property by APN
    // show address and APN
    // show Navigate button
    // reuse shared scout-result form
}
```

- [ ] **Step 5: Extract shared scout-result UI pieces from `LiveScoutScreen.kt`**

```kotlin
@Composable
internal fun ScoutResultForm(
    onSubmit: (followUp: Boolean, flyered: Boolean, notes: String) -> Unit
) { ... }
```

- [ ] **Step 6: Re-run the APN hydration test and build**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertRepositoryTest" && ./gradlew assembleDebug`

Expected: PASS, with the alert-session route compiling and loading one property by APN.

- [ ] **Step 7: Commit the alert-session UI**

```bash
git add android/app/src/main/java/com/vpt/scout/MainActivity.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/AlertedPropertyScoutScreen.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/LiveScoutScreen.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt
git commit -m "feat: add alerted property scout session"
```

## Task 5: Add User Controls and End-to-End Monitoring Flow

**Files:**
- Modify: `android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/MainActivity.kt`
- Modify: `android/app/src/main/java/com/vpt/scout/proximity/ProximityMonitorService.kt`
- Test: `android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertCoordinatorTest.kt`

- [ ] **Step 1: Write a failing test for threshold selection persistence**

```kotlin
@Test
fun `selected threshold persists as 1000 feet`() = runBlocking {
    preferences.setThresholdFeet(1000)
    assertEquals(1000, preferences.settings.first().thresholdFeet)
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.ProximityAlertCoordinatorTest" "com.vpt.scout.proximity.ProximityAlertRepositoryTest"`

Expected: FAIL until the control flow updates settings and service startup correctly.

- [ ] **Step 3: Add a `Proximity Alerts` card to `StatsScreen.kt`**

```kotlin
Text("Proximity Alerts")
FilterChip(selected = thresholdFeet == 500, onClick = { onThresholdSelected(500) }, label = { Text("500 ft") })
FilterChip(selected = thresholdFeet == 1000, onClick = { onThresholdSelected(1000) }, label = { Text("1000 ft") })
Switch(checked = enabled, onCheckedChange = onToggleEnabled)
```

- [ ] **Step 4: Start and stop the service from the UI layer**

```kotlin
if (enabled) {
    context.startForegroundService(ProximityMonitorService.startIntent(context))
} else {
    context.stopService(ProximityMonitorService.stopIntent(context))
}
```

- [ ] **Step 5: Add explicit permission handling for notifications and background location**

```kotlin
locationPermissionRequest.launch(
    arrayOf(
        Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.ACCESS_COARSE_LOCATION,
        Manifest.permission.POST_NOTIFICATIONS
    )
)
```

- [ ] **Step 6: Run the focused tests, build, and verify manually on device**

Run:

```bash
cd android && ./gradlew :app:testDebugUnitTest --tests "com.vpt.scout.proximity.*"
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Manual verification:

- enable proximity alerts
- choose `500 ft`
- background the app
- approach a known unscouted property
- verify one alert notification
- tap it and confirm the app opens the correct `alerted-scout/{apn}` session
- tap `Navigate`, return, submit the scouting result
- confirm no repeat alert for that APN

- [ ] **Step 7: Commit the end-to-end flow**

```bash
git add android/app/src/main/java/com/vpt/scout/MainActivity.kt \
  android/app/src/main/java/com/vpt/scout/ui/screens/StatsScreen.kt \
  android/app/src/main/java/com/vpt/scout/proximity/ProximityMonitorService.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertCoordinatorTest.kt \
  android/app/src/test/java/com/vpt/scout/proximity/ProximityAlertRepositoryTest.kt
git commit -m "feat: add end-to-end proximity alert flow"
```

