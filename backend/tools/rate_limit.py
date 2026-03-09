"""
In-memory rate limiting helpers for limits that don't fit slowapi
(WebSocket connections, global daily caps).

Safe for single-instance Cloud Run (max-instances=1).
"""

import os
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Global daily generate cap
# ---------------------------------------------------------------------------
_DAILY_GENERATE_LIMIT = int(os.getenv("DAILY_GENERATE_LIMIT", "20"))
_global_generate_date: date | None = None
_global_generate_count: int = 0


def check_global_generate_limit() -> tuple[bool, int]:
    """
    Returns (allowed, remaining).
    Resets at UTC midnight.
    """
    global _global_generate_date, _global_generate_count
    today = datetime.now(timezone.utc).date()
    with _lock:
        if _global_generate_date != today:
            _global_generate_date = today
            _global_generate_count = 0
        if _global_generate_count >= _DAILY_GENERATE_LIMIT:
            return False, 0
        _global_generate_count += 1
        return True, _DAILY_GENERATE_LIMIT - _global_generate_count


# ---------------------------------------------------------------------------
# Per-IP WebSocket daily limit
# ---------------------------------------------------------------------------
_MAX_WS_PER_IP_PER_DAY = int(os.getenv("MAX_WS_PER_IP_PER_DAY", "5"))
_ws_timestamps: dict[str, list[datetime]] = defaultdict(list)


def check_ws_limit(ip: str) -> bool:
    """Returns True if the WebSocket connection is allowed."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    with _lock:
        ts = _ws_timestamps[ip]
        ts[:] = [t for t in ts if t > cutoff]
        if len(ts) >= _MAX_WS_PER_IP_PER_DAY:
            return False
        ts.append(now)
        return True
