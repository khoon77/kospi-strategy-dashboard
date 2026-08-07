from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def make_report(database: str, output: str | None = None) -> dict:
    path = Path(database)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    totals = db.execute("""
      SELECT MIN(minute) first_ms, MAX(minute) last_ms, COUNT(*) price_bin_rows,
             COUNT(DISTINCT minute) covered_minutes, SUM(trade_count) trades,
             SUM(buy_quote + sell_quote) quote_volume
      FROM trade_bins
    """).fetchone()
    feeds = [dict(row) for row in db.execute("""
      SELECT venue, market, COUNT(DISTINCT minute) covered_minutes,
             COUNT(*) price_bin_rows, SUM(trade_count) trades,
             SUM(buy_quote + sell_quote) quote_volume
      FROM trade_bins GROUP BY venue, market ORDER BY venue, market
    """)]
    db.close()
    elapsed_minutes = 0
    if totals["first_ms"] is not None:
        elapsed_minutes = max(1, (totals["last_ms"] - totals["first_ms"]) / 60000 + 1)
    size = path.stat().st_size if path.exists() else 0
    projected = {}
    for days in (3, 7):
        factor = days * 1440 / elapsed_minutes if elapsed_minutes else 0
        projected[str(days)] = {
            "sqlite_bytes": round(size * factor),
            "estimated_firebase_bytes_low": round(size * factor * 0.7),
            "estimated_firebase_bytes_high": round(size * factor * 1.8)
        }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(path), "file_bytes": size,
        "first_ms": totals["first_ms"], "last_ms": totals["last_ms"],
        "elapsed_minutes": elapsed_minutes,
        "covered_minutes": totals["covered_minutes"] or 0,
        "price_bin_rows": totals["price_bin_rows"] or 0,
        "trades": totals["trades"] or 0,
        "quote_volume": totals["quote_volume"] or 0,
        "feeds": feeds, "projection": projected,
        "note": "Firebase estimate is a planning range; actual JSON/index overhead must be measured after Firebase test writes."
    }
    if output:
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="data/crypto_4h_test.sqlite3")
    parser.add_argument("--output", default="data/crypto_4h_report.json")
    args = parser.parse_args()
    print(json.dumps(make_report(args.database, args.output), ensure_ascii=False, indent=2))

