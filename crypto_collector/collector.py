from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import time
from pathlib import Path

import ccxt.pro as ccxtpro

from store import TradeStore


LOG = logging.getLogger("crypto-collector")


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Collector:
    def __init__(self, config: dict):
        self.config = config
        self.store = TradeStore(config["database"], config.get("price_bin_usdt", 25))
        self.running = True
        self.exchanges = []

    async def stream(self, feed: dict) -> None:
        venue, market = feed["name"], feed["market"]
        exchange_class = getattr(ccxtpro, feed["id"])
        exchange = exchange_class({
            "enableRateLimit": True,
            "newUpdates": True,
            "options": feed.get("options", {})
        })
        self.exchanges.append(exchange)
        seen = {}
        delay = 1
        try:
            await exchange.load_markets()
            if feed["symbol"] not in exchange.markets:
                raise RuntimeError(f"symbol not supported: {feed['symbol']}")
            market_info = exchange.market(feed["symbol"])
            contract_size = float(market_info.get("contractSize") or 1) if market_info.get("contract") else 1.0
            LOG.info("connected %s %s %s", venue, market, feed["symbol"])
            while self.running:
                try:
                    trades = await exchange.watch_trades(feed["symbol"])
                    delay = 1
                    for trade in trades:
                        stamp = int(trade.get("timestamp") or exchange.milliseconds())
                        key = trade.get("id") or f"{stamp}:{trade.get('price')}:{trade.get('amount')}:{trade.get('side')}"
                        if key in seen:
                            continue
                        seen[key] = stamp
                        # Some feeds (Binance swap in particular) occasionally emit
                        # trade-shaped messages with price/amount of 0 -- not real
                        # fills, but they'd otherwise pollute price_bin 0 with fake
                        # zero-volume rows that show up as a phantom S/R candidate.
                        price = trade.get("price")
                        raw_amount = trade.get("amount")
                        if not price or not raw_amount or price <= 0 or raw_amount <= 0:
                            continue
                        # CCXT contract trades may report amount in contracts. Normalize every feed to BTC.
                        base_amount = float(raw_amount) * contract_size
                        self.store.add_trade(venue, market, stamp, price, base_amount, trade.get("side"))
                    cutoff = exchange.milliseconds() - 120000
                    if len(seen) > 10000:
                        seen = {key: stamp for key, stamp in seen.items() if stamp >= cutoff}
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.store.record_error(venue, market, repr(exc))
                    LOG.warning("%s %s stream error: %s; retry %ss", venue, market, exc, delay)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30)
        finally:
            await exchange.close()

    async def export_loop(self) -> None:
        detail_path = self.config.get("export_detail_file", "data/crypto_bins_recent.json")
        rollup_path = self.config.get("export_rollup_file", "data/crypto_bins_hourly.json")
        status_path = self.config.get("export_status_file", "data/crypto_status.json")
        detail_hours = self.config.get("export_detail_hours", 72)
        retention_days = self.config.get("retention_days", 90)
        tick = 0
        while self.running:
            self.store.prune(retention_days)
            self.store.export_detail(detail_path, hours=detail_hours)
            self.store.export_status(status_path)
            # Rollup covers the whole retention window and barely changes minute to
            # minute, so it only needs re-exporting every 5th tick (~5 min).
            if tick % 5 == 0:
                self.store.export_rollup(rollup_path, days=retention_days)
            tick += 1
            await asyncio.sleep(60)

    async def run(self) -> None:
        tasks = [asyncio.create_task(self.stream(feed)) for feed in self.config["venues"]]
        tasks.append(asyncio.create_task(self.export_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.store.export_detail(self.config.get("export_detail_file", "data/crypto_bins_recent.json"),
                                      hours=self.config.get("export_detail_hours", 72))
            self.store.export_rollup(self.config.get("export_rollup_file", "data/crypto_bins_hourly.json"),
                                      days=self.config.get("retention_days", 90))
            self.store.export_status(self.config.get("export_status_file", "data/crypto_status.json"))
            self.store.close()


async def main(config_path: str, duration: int = 0) -> None:
    collector = Collector(load_config(config_path))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: setattr(collector, "running", False))
        except NotImplementedError:
            pass
    task = asyncio.create_task(collector.run())
    if duration:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=duration)
        except asyncio.TimeoutError:
            collector.running = False
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    else:
        await task


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect normalized BTC trades from five exchanges")
    parser.add_argument("--config", default="crypto_collector/config.json")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--duration", type=int, default=0, help="Stop after N seconds (for testing)")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main(args.config, args.duration))
