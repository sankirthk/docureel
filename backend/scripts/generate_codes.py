#!/usr/bin/env python3
"""
Generate invite codes and write them to Firestore.

Usage:
    python scripts/generate_codes.py --count 10 --max-uses 1 --expires-in 48h --label launch

Reads GOOGLE_CLOUD_PROJECT from the environment (or .env in the repo root).
"""

import argparse
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(override=True)

_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")


def _parse_duration(value: str) -> timedelta:
    m = re.fullmatch(r"(\d+)(h|d)", value.strip())
    if not m:
        raise ValueError(f"Cannot parse duration '{value}'. Use e.g. 48h or 7d.")
    n = int(m.group(1))
    return timedelta(hours=n) if m.group(2) == "h" else timedelta(days=n)


def _random_code() -> str:
    return str(uuid.uuid4())


def main():
    parser = argparse.ArgumentParser(description="Generate invite codes in Firestore.")
    parser.add_argument("--count", type=int, default=1, help="Number of codes to generate")
    parser.add_argument("--max-uses", type=int, default=1, help="Max redemptions per code")
    parser.add_argument("--expires-in", type=str, default=None, help="Expiry duration, e.g. 48h or 7d")
    parser.add_argument("--label", type=str, default="", help="Human-readable label for this batch")
    args = parser.parse_args()

    if not _PROJECT:
        print("ERROR: GOOGLE_CLOUD_PROJECT not set.")
        raise SystemExit(1)

    from google.cloud import firestore

    expires_at = None
    if args.expires_in:
        expires_at = datetime.now(tz=timezone.utc) + _parse_duration(args.expires_in)

    db = firestore.Client(project=_PROJECT)
    col = db.collection("invite_codes")
    now = datetime.now(tz=timezone.utc)

    codes = []
    for _ in range(args.count):
        code = _random_code()
        doc = {
            "label": args.label,
            "max_uses": args.max_uses,
            "use_count": 0,
            "created_at": now,
        }
        if expires_at:
            doc["expires_at"] = expires_at
        col.document(code.lower()).set(doc)
        codes.append(code)

    print(f"Created {len(codes)} invite code(s):")
    for c in codes:
        print(f"  {c}")


if __name__ == "__main__":
    main()
