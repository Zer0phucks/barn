#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import enrichment_runner as _impl  # type: ignore

enrichment_state = _impl.enrichment_state
bill_needs_enrichment = _impl.bill_needs_enrichment
build_enrichment_queue = _impl.build_enrichment_queue
get_bills_needing_enrichment = _impl.get_bills_needing_enrichment
get_enrichment_state = _impl.get_enrichment_state
start_enrichment = _impl.start_enrichment
enrich_property = _impl.enrich_property
