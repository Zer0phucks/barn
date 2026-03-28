# Repository Guidelines

## Project Structure & Module Organization
BARN is a monorepo. `web/` contains the Vite + React + TypeScript site; app code lives in `web/src`, tests in `web/src/test`, and Supabase assets in `web/supabase/`. `scan/` contains the Python scanner and Flask UI, with reusable modules in `scan/scanner/`, tests in `scan/tests/`, and service units in `scan/service/`. `android/` contains the Kotlin Scout app under `android/app/src/main` with JVM tests in `android/app/src/test`. Root `deploy.sh` and `scripts/` handle deployment and maintenance.

## Build, Test, and Development Commands
- `cd web && npm install && npm run dev` starts the web app locally.
- `cd web && npm run build`, `npm run lint`, `npm run test` build, lint, and run Vitest once.
- `cd scan && ./install.sh` creates `.venv`, installs Python deps, and installs Playwright Chromium.
- `cd scan && source .venv/bin/activate && python run_all.py --city=OAKLAND` runs the scanner plus Flask UI.
- `cd scan && source .venv/bin/activate && python -m unittest discover -s tests` runs scanner tests.
- `cd android && ./gradlew test` runs JVM tests; `cd android && ./gradlew assembleDebug` builds a debug APK.

## Coding Style & Naming Conventions
Follow the existing style in each app. In `web/`, use 2-space indentation, PascalCase for components/pages (`AdminDashboard.tsx`), camelCase for helpers, and keep shared primitives in `web/src/components/ui/`. In `scan/`, use 4-space indentation, type hints where practical, snake_case module names, and keep reusable logic in `scan/scanner/`. In `android/`, use Kotlin conventions: 4-space indentation, PascalCase types, and package names under `com.vpt.scout`. Do not hand-edit `web/src/integrations/supabase/types.ts`.

## Testing Guidelines
Web tests use Vitest with jsdom and should follow `src/**/*.{test,spec}.{ts,tsx}`. Python tests use `unittest` and should be named `test_*.py`. Android unit tests use JUnit4 and should end with `Test.kt`. Any behavior change should include or update the nearest relevant test.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, `style:`, and `chore:`. Keep messages imperative and concise, for example `fix: disambiguate get_bills_filtered rpc overloads`. PRs should state which surface changed (`web`, `scan`, `android`), list verification steps run, note any env/schema/service changes, and include screenshots for user-facing UI updates.

## Security & Configuration Tips
Never commit `.env` files, Supabase keys, `MAPS_API_KEY`, or deploy SSH secrets. Scanner setup may require `playwright install chromium` after dependency changes. Android local secrets belong in `android/local.properties`; web and scan secrets belong in local `.env` files.
