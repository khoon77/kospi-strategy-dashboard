import tempfile
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


if __name__ == "__main__":
    unittest.main()
