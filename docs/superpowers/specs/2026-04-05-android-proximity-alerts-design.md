# Android Proximity Alerts Design

**Date:** 2026-04-05
**Status:** Draft for review
**Scope:** `android/` background scouting workflow

## Summary

The Android Scout app should support a background proximity-monitoring mode that alerts the user when they are within a chosen distance of the nearest unscouted property. The first release should support thresholds like `500 ft` and `1000 ft`, track only the closest eligible property at a time, and open a dedicated in-app scout session when the user taps the notification.

This feature is intended to make field scouting more proactive. Instead of requiring the user to constantly check the app, Android should monitor in the background, surface the nearest unscouted target, and preserve the full scouting flow inside the app so the user can navigate to the property and later record the scouting result for that same property.

## Goals

- Alert the user in the background when they come within a configured distance of the nearest unscouted property.
- Limit alerts to the closest property only to avoid noisy notifications in dense neighborhoods.
- Keep the scouting workflow inside the Android app when the user taps the alert.
- Let the user launch navigation to the alerted property from the in-app scout session.
- Prevent repeated alerts for properties that have already been scouted.

## Non-Goals

- Notify for every nearby property.
- Support large-scale Android geofence registration for all properties.
- Build route prediction or multi-stop planning in the first release.
- Add scanner worker-control features to the background flow.

## User Experience

The user enables proximity alerts in the app and chooses a simple threshold such as `500 ft` or `1000 ft`. While monitoring is enabled, Android shows the required foreground-service notification to indicate that proximity monitoring is active.

When the user gets close enough to the nearest unscouted property, Android posts an alert notification. Tapping that notification should not jump directly into Google Maps. Instead, it should open a dedicated single-property scout session screen inside the app. That screen should show the property details, allow the user to launch Google Maps navigation, and preserve the exact property context so the user can come back and record the scouting result after visiting it.

## Architecture

### Recommended Approach

Use a foreground location-tracking service backed by the existing Android app and Supabase-based data layer.

This is the recommended approach because:

- it is reliable for near-real-time proximity detection
- it works better than periodic workers for field movement
- it avoids the platform limits of registering geofences for large changing property sets
- it keeps the alerting feature fully under the app's control

### High-Level Architecture

The feature should consist of:

- a foreground monitoring service for continuous location-based evaluation
- a proximity repository that determines the nearest eligible unscouted property
- local preferences for monitoring state and alert suppression
- a notification manager for both persistent monitoring and triggered alerts
- a dedicated single-property scout session screen opened from alert notifications

The service should operate independently of whether the Properties, Map, or Scout screens are currently visible.

## Component Design

### `ProximityMonitorService`

This service is the runtime engine for monitoring. It should:

- run as a foreground service while proximity alerts are enabled
- request location updates at a reasonable field-usage cadence
- ask the repository for the nearest unscouted property
- compare that property's distance to the active threshold
- post exactly one alert for the active closest property when the user enters the threshold
- suppress duplicate alerts until the user exits the zone or the property becomes scouted

### `ProximityAlertRepository`

This repository should answer one core question efficiently:

> What is the nearest unscouted property to the user's current location?

For the first release, it can build on the Android app's existing Supabase-backed property data and local cached marker/property state. The repository should exclude already-scouted APNs and rows without coordinates, then return the nearest eligible property with enough information to drive the alert and scout session.

If query scale becomes a problem later, this repository can be upgraded to use a dedicated Supabase RPC for nearest-unscouted selection.

### `ProximityAlertPreferences`

This component should persist:

- whether monitoring is enabled
- the selected threshold distance
- the last alerted APN
- any cooldown or exit-radius state needed to avoid repeated notifications

Preferences should survive app restarts so monitoring state remains consistent.

### `ProximityNotificationManager`

This manager should own:

- the persistent foreground notification while monitoring is active
- the alert notification when the threshold is crossed

The alert notification should carry enough payload to reopen the app directly into the single-property scout session for the alerted APN.

### `AlertedPropertyScoutScreen`

This should be a new dedicated screen or a strongly specialized mode of the existing scout UI. Its job is to represent one specific alerted property rather than a sequence of nearby properties.

It should include:

- property summary
- distance/context if available
- `Navigate` action to Google Maps
- scouting result entry
- dismiss/skip behavior

The important distinction is that this screen preserves the alert target so the user can return from navigation and still record findings against the same APN.

## Data Flow

### Monitoring

1. User enables proximity alerts and selects a threshold.
2. Android starts the foreground monitoring service.
3. The service receives location updates.
4. The repository determines the nearest unscouted property.
5. If that property is within the threshold and has not already been alerted, the service posts an alert notification.

### Alert Handling

1. User taps the alert notification.
2. Android opens the app into the dedicated single-property scout session.
3. The session loads the alerted property by APN and shows the property details.
4. User can tap `Navigate` to open Google Maps.
5. After visiting the property, the user returns to the app and records the scouting result.
6. The app writes the result to `scout_results`.
7. That APN is no longer eligible for future proximity alerts.

### Duplicate Suppression

The service should only alert for the closest property at a time. After an alert is sent, the app should suppress additional alerts for that APN until one of these happens:

- the property is marked as scouted
- the user moves back outside an exit radius
- the active nearest property changes and the previous one is no longer the monitored target

## Permissions and Platform Behavior

This feature requires Android location handling that is more explicit than the current app.

The app will need to support:

- foreground location permission
- background location permission where required by Android version and chosen service behavior
- foreground service support for continuous monitoring
- notification permission on recent Android versions

The UI should make monitoring opt-in and explain clearly that Android will show a persistent monitoring notification while the feature is enabled.

## Error Handling

The feature should fail quietly but transparently.

Expected cases:

- missing location permission
- background location denied
- notifications denied
- temporary loss of location updates
- Supabase unavailable
- alerted property already scouted by the time the user opens it
- Google Maps unavailable on the device

Expected behavior:

- if required permissions are missing, monitoring should stay off and explain what is needed
- if location is temporarily unavailable, the service should remain active but show a waiting/paused state rather than pretending alerts are working
- if the property is stale by the time the session opens, the app should tell the user it has already been scouted and allow dismissal
- if Google Maps is unavailable, navigation should fall back to a browser maps URL

## Testing

### Repository and Service Tests

Add tests for:

- nearest unscouted property selection
- threshold entry behavior
- closest-only suppression
- duplicate-alert prevention
- stop-alerting-on-scouted behavior

### Notification Routing Tests

Add tests proving that:

- alert notifications carry the correct APN
- tapping the alert opens the dedicated scout session
- the session loads the expected property

### Session Flow Tests

Add tests for:

- launching navigation from the alerted-property screen
- returning to record the scouting result
- marking the property scouted and making it ineligible for future alerts

### Manual Device Verification

Because this feature depends on Android process and background behavior, manual device verification is required:

- enable monitoring
- background the app
- approach a known unscouted property
- verify one alert is posted
- tap the alert
- confirm the app opens the correct single-property scout session
- launch navigation and return
- submit scouting result
- confirm no repeat alert for that APN

## Rollout

The first release should stay intentionally narrow:

- thresholds limited to `500 ft` and `1000 ft`
- closest property only
- one active alerted target at a time
- no geofence batching
- no advanced route planning

This keeps the behavior understandable and allows us to validate the field workflow before expanding the feature.
