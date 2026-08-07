from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS trade_bins (
  minute INTEGER NOT NULL,
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  price_bin REAL NOT NULL,
  buy_base REAL NOT NULL DEFAULT 0,
  sell_base REAL NOT NULL DEFAULT 0,
  buy_quote REAL NOT NULL DEFAULT 0,
  sell_quote REAL NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (minute, venue, market, price_bin)
);
CREATE TABLE IF NOT EXISTS collector_status (
  venue TEXT NOT NULL,
  market TEXT NOT NULL,
  last_trade_ms INTEGER,
  last_receive_ms INTEGER,
  messages INTEGER NOT NULL DEFAULT 0,
  errors INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  PRIMARY KEY (venue, market)
);
CREATE INDEX IF NOT EXISTS idx_trade_bins_minute ON trade_bins(minute);
"""


class TradeStore:
    def __init__(self, path: str | Path, price_bin: float = 25):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.price_bin = float(price_bin)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def bucket_price(self, price: float) -> float:
        return math.floor(float(price) / self.price_bin) * self.price_bin

    def add_trade(self, venue: str, market: str, timestamp_ms: int, price: float,
                  amount: float, side: str | None) -> None:
        minute = int(timestamp_ms // 60000 * 60000)
        price_level = self.bucket_price(price)
        quote = float(price) * float(amount)
        is_buy = str(side).lower() == "buy"
        values = (float(amount), 0.0, quote, 0.0) if is_buy else (0.0, float(amount), 0.0, quote)
        now_ms = int(time.time() * 1000)
        with self.lock, self.db:
            self.db.execute("""
              INSERT INTO trade_bins(minute,venue,market,price_bin,buy_base,sell_base,buy_quote,sell_quote,trade_count)
              VALUES(?,?,?,?,?,?,?,?,1)
              ON CONFLICT(minute,venue,market,price_bin) DO UPDATE SET
                buy_base=buy_base+excluded.buy_base,
                sell_base=sell_base+excluded.sell_base,
                buy_quote=buy_quote+excluded.buy_quote,
                sell_quote=sell_quote+excluded.sell_quote,
                trade_count=trade_count+1
            """, (minute, venue, market, price_level, *values))
            self.db.execute("""
              INSERT INTO collector_status(venue,market,last_trade_ms,last_receive_ms,messages,errors)
              VALUES(?,?,?,?,1,0)
              ON CONFLICT(venue,market) DO UPDATE SET
                last_trade_ms=excluded.last_trade_ms,
                last_receive_ms=excluded.last_receive_ms,
                messages=messages+1,
                last_error=NULL
            """, (venue, market, int(timestamp_ms), now_ms))

    def record_error(self, venue: str, market: str, message: str) -> None:
        now_ms = int(time.time() * 1000)
        with self.lock, self.db:
            self.db.execute("""
              INSERT INTO collector_status(venue,market,last_receive_ms,messages,errors,last_error)
              VALUES(?,?,?,0,1,?)
              ON CONFLICT(venue,market) DO UPDATE SET
                last_receive_ms=excluded.last_receive_ms,
                errors=errors+1,
                last_error=excluded.last_error
            """, (venue, market, now_ms, message[:500]))

    def profile(self, minutes: int, venue: str = "all", market: str = "all") -> dict:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(minutes) * 60000
        clauses, params = ["minute >= ?"], [start_ms]
        if venue != "all":
            clauses.append("venue = ?")
            params.append(venue)
        if market != "all":
            clauses.append("market = ?")
            params.append(market)
        where = " AND ".join(clauses)
        with self.lock:
            rows = self.db.execute(f"""
              SELECT price_bin, SUM(buy_base) buy_base, SUM(sell_base) sell_base,
                     SUM(buy_quote) buy_quote, SUM(sell_quote) sell_quote,
                     SUM(trade_count) trade_count
              FROM trade_bins WHERE {where}
              GROUP BY price_bin ORDER BY price_bin
            """, params).fetchall()
            breakdown = self.db.execute(f"""
              SELECT venue, market, SUM(buy_quote) buy_quote, SUM(sell_quote) sell_quote,
                     SUM(trade_count) trade_count, MIN(minute) first_minute, MAX(minute) last_minute
              FROM trade_bins WHERE {where}
              GROUP BY venue, market ORDER BY venue, market
            """, params).fetchall()
            statuses = self.db.execute("SELECT * FROM collector_status ORDER BY venue,market").fetchall()
        bins = [dict(row) for row in rows]
        for row in bins:
            row["total_quote"] = row["buy_quote"] + row["sell_quote"]
            row["delta_quote"] = row["buy_quote"] - row["sell_quote"]
        total = sum(row["total_quote"] for row in bins)
        poc = max(bins, key=lambda row: row["total_quote"], default=None)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_minutes": int(minutes), "venue": venue, "market": market,
            "price_bin_usdt": self.price_bin, "total_quote": total,
            "buy_quote": sum(row["buy_quote"] for row in bins),
            "sell_quote": sum(row["sell_quote"] for row in bins),
            "trade_count": sum(row["trade_count"] for row in bins),
            "poc": poc["price_bin"] if poc else None,
            "bins": bins, "breakdown": [dict(row) for row in breakdown],
            "status": [dict(row) for row in statuses]
        }

    def export(self, path: str | Path, windows=(15, 30, 60, 240)) -> dict:
        venues = [row[0] for row in self.db.execute("SELECT DISTINCT venue FROM collector_status ORDER BY venue")]
        selections = [("all", "all"), ("all", "spot"), ("all", "swap")]
        selections += [(venue, market) for venue in venues for market in ("all", "spot", "swap")]
        payload = {
            "schema_version": 1,
            "source": "CCXT Pro public trade WebSockets",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profiles": {
                str(m): {f"{venue}|{market}": self.profile(m, venue, market)
                         for venue, market in selections}
                for m in windows
            }
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp.replace(target)
        return payload

    def _bin_header(self) -> tuple[dict, dict, dict]:
        venues = [r[0] for r in self.db.execute(
            "SELECT DISTINCT venue FROM trade_bins ORDER BY venue")]
        markets = [r[0] for r in self.db.execute(
            "SELECT DISTINCT market FROM trade_bins ORDER BY market")]
        header = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "price_bin_usdt": self.price_bin,
            "venues": venues,
            "markets": markets,
            # bin row = [time_ms, venue_idx, market_idx, price_bin, buy_base, sell_base, buy_quote, sell_quote, trade_count]
        }
        return header, {v: i for i, v in enumerate(venues)}, {m: i for i, m in enumerate(markets)}

    def export_detail(self, path: str | Path, hours: int = 72) -> None:
        """1-minute granularity, recent history only -- small enough to ship whole.

        Client-side range aggregation (zoom-following volume profile) uses this for
        any visible range that falls within the last `hours`; see export_rollup for
        older history.
        """
        cutoff = int(time.time() * 1000) - hours * 3600000
        with self.lock:
            header, v_idx, m_idx = self._bin_header()
            rows = self.db.execute("""
              SELECT minute, venue, market, price_bin, buy_base, sell_base,
                     buy_quote, sell_quote, trade_count
              FROM trade_bins WHERE minute >= ?
            """, (cutoff,)).fetchall()
        bins = [
            [r["minute"], v_idx[r["venue"]], m_idx[r["market"]], r["price_bin"],
             round(r["buy_base"], 6), round(r["sell_base"], 6),
             round(r["buy_quote"], 2), round(r["sell_quote"], 2), r["trade_count"]]
            for r in rows
        ]
        self._write_json(path, {**header, "granularity_ms": 60000, "covers_from": cutoff, "bins": bins})

    def export_rollup(self, path: str | Path, days: int = 90) -> None:
        """1-hour granularity, covers the full retention window.

        Price-bin totals are exact either way -- only the time-bucket width changes,
        so pre-summing to the hour loses nothing for a volume-at-price histogram. Only
        matters for slicing a range at sub-hour precision, which export_detail covers
        for anything recent.
        """
        cutoff = int(time.time() * 1000) - days * 86400000
        with self.lock:
            header, v_idx, m_idx = self._bin_header()
            rows = self.db.execute("""
              SELECT (minute / 3600000) * 3600000 AS hour, venue, market, price_bin,
                     SUM(buy_base) buy_base, SUM(sell_base) sell_base,
                     SUM(buy_quote) buy_quote, SUM(sell_quote) sell_quote,
                     SUM(trade_count) trade_count
              FROM trade_bins WHERE minute >= ?
              GROUP BY hour, venue, market, price_bin
            """, (cutoff,)).fetchall()
        bins = [
            [r["hour"], v_idx[r["venue"]], m_idx[r["market"]], r["price_bin"],
             round(r["buy_base"], 6), round(r["sell_base"], 6),
             round(r["buy_quote"], 2), round(r["sell_quote"], 2), r["trade_count"]]
            for r in rows
        ]
        self._write_json(path, {**header, "granularity_ms": 3600000, "covers_from": cutoff, "bins": bins})

    def export_status(self, path: str | Path) -> None:
        """Tiny, cheap file (10 rows) so the dashboard can show feed health without
        pulling in the much larger bin exports just to check who's stale."""
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM collector_status ORDER BY venue, market").fetchall()
        self._write_json(path, {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": [dict(row) for row in rows],
        })

    @staticmethod
    def _write_json(path: str | Path, payload: dict) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp.replace(target)

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def prune(self, days: int = 90) -> int:
        cutoff = int((time.time() - days * 86400) * 1000)
        with self.lock, self.db:
            cursor = self.db.execute("DELETE FROM trade_bins WHERE minute < ?", (cutoff,))
        return cursor.rowcount
