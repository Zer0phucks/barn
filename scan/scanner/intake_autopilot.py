#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import intake_autopilot as _impl  # type: ignore

PARCELS_CSV_PATH = _impl.PARCELS_CSV_PATH
LEGACY_PARCELS_CSV_PATH = _impl.LEGACY_PARCELS_CSV_PATH
intake_state = _impl.intake_state
get_intake_state = _impl.get_intake_state
start_daily_intake = _impl.start_daily_intake
run_daily_intake = _impl.run_daily_intake
should_promote_property = _impl.should_promote_property
reconcile_backlog_rows = _impl.reconcile_backlog_rows
write_backlog_csv = _impl.write_backlog_csv
