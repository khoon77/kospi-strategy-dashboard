import json
import tempfile
import time
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "crypto_collector"))
from store import TradeStore


class TradeStoreTest(unittest.TestCase):
    def test_aggregates_venue_market_price_and_side(self):
        with tempfile.TemporaryDirectory() as folder:
            store = TradeStore(Path(folder) / "test.sqlite3", 25)
            now = __import__("time").time_ns() // 1_000_000
            store.add_trade("Binance", "spot", now, 100012, 1.0, "buy")
            store.add_trade("Binance", "spot", now, 100024, 2.0, "sell")
            store.add_trade("Bybit", "swap", now, 100026, 0.5, "buy")
            all_data = store.profile(15)
            self.assertEqual(all_data["trade_count"], 3)
            self.assertEqual(len(all_data["bins"]), 2)
            self.assertAlmostEqual(all_data["buy_quote"], 150025)
            binance = store.profile(15, "Binance", "spot")
            self.assertEqual(binance["trade_count"], 2)
            self.assertEqual(binance["bins"][0]["price_bin"], 100000)
            self.assertLess(binance["bins"][0]["delta_quote"], 0)
            store.close()

    def test_export_detail_and_rollup_for_client_side_range_aggregation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = TradeStore(Path(folder) / "test.sqlite3", 25)
            now_ms = time.time_ns() // 1_000_000
            hour = now_ms // 3600000 * 3600000
            # Anchored 5-6 minutes into the current hour rather than at "now" --
            # two real timestamps one minute apart would occasionally straddle an
            # hour boundary (flaky ~1/60 runs), landing in two rollup buckets
            # instead of one. Same price bin either way -- rollup must sum them
            # into a single hourly row even though detail keeps them as two rows.
            minute = hour + 5 * 60000
            store.add_trade("Binance", "spot", minute, 100012, 1.0, "buy")
            store.add_trade("Binance", "spot", minute + 60000, 100013, 2.0, "buy")

            detail_path = Path(folder) / "detail.json"
            rollup_path = Path(folder) / "rollup.json"
            store.export_detail(detail_path, hours=1)
            store.export_rollup(rollup_path, days=1)

            detail = json.loads(detail_path.read_text(encoding="utf-8"))
            self.assertEqual(detail["venues"], ["Binance"])
            self.assertEqual(detail["markets"], ["spot"])
            self.assertEqual(len(detail["bins"]), 2)
            row = detail["bins"][0]
            self.assertEqual(row[1], 0)  # venue_idx -> Binance
            self.assertEqual(row[2], 0)  # market_idx -> spot
            self.assertEqual(row[3], 100000)  # price_bin

            rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
            self.assertEqual(len(rollup["bins"]), 1)
            self.assertEqual(rollup["bins"][0][0], hour)
            self.assertAlmostEqual(rollup["bins"][0][4], 3.0)  # buy_base summed
            self.assertEqual(rollup["bins"][0][8], 2)  # trade_count summed
            store.close()


if __name__ == "__main__":
    unittest.main()
