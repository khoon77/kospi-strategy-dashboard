from __future__ import annotations

import argparse
import asyncio

import ccxt.pro as ccxtpro

from collector import load_config


async def check(feed: dict, timeout: int) -> tuple[str, bool, str]:
    label = f"{feed['name']} {feed['market']}"
    exchange = getattr(ccxtpro, feed["id"])({
        "enableRateLimit": True, "newUpdates": True, "options": feed.get("options", {})
    })
    try:
        await exchange.load_markets()
        if feed["symbol"] not in exchange.markets:
            return label, False, f"unsupported symbol {feed['symbol']}"
        trades = await asyncio.wait_for(exchange.watch_trades(feed["symbol"]), timeout=timeout)
        return label, bool(trades), f"received {len(trades)} trade(s)"
    except Exception as exc:
        return label, False, f"{type(exc).__name__}: {exc}"
    finally:
        await exchange.close()


async def main(path: str, timeout: int) -> int:
    feeds = load_config(path)["venues"]
    results = await asyncio.gather(*(check(feed, timeout) for feed in feeds))
    for label, ok, message in results:
        print(f"{'OK' if ok else 'FAIL':4} {label:20} {message}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe all configured public trade WebSockets")
    parser.add_argument("--config", default="crypto_collector/config.example.json")
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.config, args.timeout)))
