# Android Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add broad automated coverage for the Android app and validate core workflows on-device with the Android MCP server.

**Architecture:** Expand JVM coverage around auth, repositories, and mapping helpers using fakes and `MockWebServer`, then add Compose instrumentation tests for key screens and user flows. Keep production changes limited to small testability seams where the current code is too tightly coupled to platform objects.

**Tech Stack:** Kotlin, JUnit4, MockWebServer, Jetpack Compose UI Test, Android instrumentation, Android MCP

---

## File Structure

- Modify: `android/app/build.gradle.kts`
- Modify: `android/app/src/main/java/com/vpt/scout/SupabaseAuthManager.kt`
- Modify: `android/app/src/test/java/com/vpt/scout/SupabaseRepositoryTest.kt`
- Create: `android/app/src/test/java/com/vpt/scout/SupabaseAuthManagerTest.kt`
- Create: `android/app/src/androidTest/java/com/vpt/scout/AppWorkflowTest.kt`

## Tasks

### Task 1: Strengthen JVM Coverage

- [ ] Add failing tests for auth login, refresh, and sign-out behavior.
- [ ] Add failing tests for repository pagination, state updates, and marker mapping helpers.
- [ ] Refactor only the seams needed for testability.
- [ ] Re-run focused JVM tests until green.

### Task 2: Add Compose Workflow Coverage

- [ ] Add instrumentation tests for login, list management UI, and property-screen scout actions.
- [ ] Prefer existing labels/content descriptions before adding new UI-only hooks.
- [ ] Re-run focused instrumentation tests until green.

### Task 3: Verify Real Workflows

- [ ] Build and install the Android app.
- [ ] Use the Android MCP server to open the app and exercise login shell and navigation flows.
- [ ] Record blockers separately from automated test failures.

### Task 4: Final Verification

- [ ] Run `cd android && ./gradlew test`
- [ ] Run `cd android && ./gradlew connectedDebugAndroidTest` if the device/emulator is compatible.
- [ ] Check lints for edited files.
