#!/usr/bin/env python3
"""Restart the collector if every feed has gone quiet.

systemd's Restart=always only fires when the process actually exits/crashes.
It does not help if the asyncio loop is alive but every websocket has silently
stalled (rare, but seen with flaky exchange connections). This script checks
the same collector_status table the dashboard reads and, if ALL feeds have
been silent past the threshold, restarts the systemd unit. A single stale
feed does NOT trigger this -- collector.py's own backoff already retries
individual feeds; that's normal operation, not a hang.
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="data/crypto_trades.sqlite3")
    parser.add_argument("--service", default="collector@ubuntu.service")
    parser.add_argument("--stale-seconds", type=int, default=300)
    args = parser.parse_args()

    db = sqlite3.connect(args.database)
    rows = db.execute("SELECT venue, market, last_receive_ms FROM collector_status").fetchall()
    db.close()

    if not rows:
        print("no collector_status rows yet; leaving it to boot")
        return 0

    now_ms = int(time.time() * 1000)
    stale = [r for r in rows if not r[2] or now_ms - r[2] > args.stale_seconds * 1000]

    if len(stale) < len(rows):
        return 0  # at least one feed is alive; the loop itself is not hung

    print(f"all {len(rows)} feeds silent for >{args.stale_seconds}s, restarting {args.service}", file=sys.stderr)
    subprocess.run(["systemctl", "restart", args.service], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
