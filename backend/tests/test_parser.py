"""
Quick test for ParserAgent — run directly without starting the server.

Usage:
  cd backend
  python tests/test_parser.py path/to/report.pdf
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from agents.parser import _parse_with_gemini
from models.manifest import Manifest
from tools.gemini import build_client
from pydantic import ValidationError


async def test(pdf_path: str):
    print(f"Parsing: {pdf_path}\n")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    client = build_client()

    print("Sending to Gemini 3.1 Pro...")
    raw = _parse_with_gemini(pdf_bytes, client)

    print("\n--- Raw JSON from model ---")
    print(json.dumps(raw, indent=2))

    print("\n--- Pydantic validation ---")
    try:
        manifest = Manifest.model_validate(raw)
        print(f"✓ Valid manifest")
        print(f"  Title:     {manifest.title}")
        print(f"  Type:      {manifest.type}")
        print(f"  Pages:     {manifest.total_pages}")
        print(f"  Sections:  {len(manifest.key_sections)}")
        print(f"  Sentiment: {manifest.sentiment}")
        print(f"\n  Summary: {manifest.overall_summary}")
        print(f"\n  Sections:")
        for s in manifest.key_sections:
            print(f"    [{s.id}] {s.heading} (p.{s.page})")
            print(f"         {s.summary[:80]}...")
            print(f"         Stats: {s.key_stats}")
    except ValidationError as e:
        print(f"✗ Validation failed:\n{e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_parser.py path/to/report.pdf")
        sys.exit(1)

    asyncio.run(test(sys.argv[1]))
