#!/usr/bin/env python3
"""
Run all Phase 15 QA checks.

Usage:
    python scripts/qa_all.py
    python scripts/qa_all.py --strict
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "qa_reports"


def run(cmd):
    print()
    print("[qa-all] " + " ".join(str(x) for x in cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    content_cmd = [
        sys.executable,
        "scripts/validate_content.py",
        "--json-out", str(REPORT_DIR / "content_qa.json"),
        "--markdown-out", str(REPORT_DIR / "content_qa.md"),
    ]
    if args.strict:
        content_cmd.append("--strict")

    rc_content = run(content_cmd)
    rc_db = run([
        sys.executable,
        "scripts/audit_database.py",
        "--json-out", str(REPORT_DIR / "database_qa.json"),
    ])

    print()
    print("[qa-all] ========================================")
    print(f"[qa-all] Static content QA exit code: {rc_content}")
    print(f"[qa-all] Database audit exit code: {rc_db}")
    print(f"[qa-all] Reports directory: {REPORT_DIR}")

    if rc_content == 0 and rc_db == 0:
        print("[qa-all] RESULT: PASS")
        return 0

    print("[qa-all] RESULT: REVIEW REQUIRED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
