from __future__ import annotations

import sys
from pathlib import Path


_TESTS_DIR = Path(__file__).resolve().parent
_OMS_AGENT_DIR = _TESTS_DIR.parent
_BATCH_REALLOCATION_SCRIPTS = _OMS_AGENT_DIR.parent / "batch-reallocation" / "scripts"

if str(_BATCH_REALLOCATION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_BATCH_REALLOCATION_SCRIPTS))
