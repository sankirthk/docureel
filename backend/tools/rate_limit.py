"""
In-memory rate limiting helpers for limits that don't fit slowapi
(WebSocket connections, global daily caps).

Safe for single-instance Cloud Run (max-instances=1).
"""

import os
import threading
from collections import defaultdict
from dataclasses import dataclass
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
# Per-IP auth failure lockout (brute-force protection)
# ---------------------------------------------------------------------------
# After N failures the IP is locked out for an increasing duration:
#   5 failures  →  15 min lockout
#   10 failures →  1 h lockout
#   15 failures →  6 h lockout
#   20+ failures → 24 h lockout

_AUTH_LOCKOUT_THRESHOLDS: list[tuple[int, timedelta]] = [
    (20, timedelta(hours=24)),
    (15, timedelta(hours=6)),
    (10, timedelta(hours=1)),
    (5,  timedelta(minutes=15)),
]


@dataclass
class _AuthRecord:
    failures: int = 0
    locked_until: datetime | None = None


_auth_records: dict[str, _AuthRecord] = defaultdict(_AuthRecord)


def check_auth_lockout(ip: str) -> tuple[bool, str | None]:
    """
    Returns (allowed, error_message).
    allowed=False means the IP is locked out; error_message explains why.
    Call record_auth_failure() when the code is wrong.
    """
    with _lock:
        rec = _auth_records[ip]
        now = datetime.now(timezone.utc)
        if rec.locked_until and now < rec.locked_until:
            remaining = int((rec.locked_until - now).total_seconds() / 60) + 1
            return False, f"Too many failed attempts. Try again in {remaining} minute(s)."
        return True, None


def record_auth_failure(ip: str) -> None:
    """Increment failure count and apply lockout if a threshold is crossed."""
    with _lock:
        rec = _auth_records[ip]
        rec.failures += 1
        now = datetime.now(timezone.utc)
        for threshold, duration in _AUTH_LOCKOUT_THRESHOLDS:
            if rec.failures >= threshold:
                rec.locked_until = now + duration
                break


def record_auth_success(ip: str) -> None:
    """Reset failure count on successful auth."""
    with _lock:
        _auth_records.pop(ip, None)


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
