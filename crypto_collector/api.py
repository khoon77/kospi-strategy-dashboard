from __future__ import annotations

import argparse
import time
from pathlib import Path

import ccxt.async_support as ccxt
from aiohttp import web

from collector import load_config
from store import TradeStore


def create_app(config: dict) -> web.Application:
    store = TradeStore(config["database"], config.get("price_bin_usdt", 25))
    app = web.Application()
    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    candle_cache: dict[str, tuple[float, list[list[float]]]] = {}

    async def profile(request: web.Request) -> web.Response:
        minutes = min(10080, max(1, int(request.query.get("minutes", "60"))))
        venue = request.query.get("venue", "all")
        market = request.query.get("market", "all")
        response = web.json_response(store.profile(minutes, venue, market))
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "no-store"
        return response

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "database": str(Path(config["database"]).resolve())})

    async def candles(request: web.Request) -> web.Response:
        timeframe = request.query.get("timeframe", "1h")
        if timeframe not in {"15m", "30m", "1h", "4h"}:
            raise web.HTTPBadRequest(text="unsupported timeframe")
        limit = min(500, max(50, int(request.query.get("limit", "300"))))
        cached = candle_cache.get(timeframe)
        if cached and time.time() - cached[0] < 15 and len(cached[1]) >= limit:
            rows = cached[1][-limit:]
        else:
            try:
                rows = await exchange.fetch_ohlcv("BTC/USDT:USDT", timeframe=timeframe, limit=limit)
            except Exception as exc:
                raise web.HTTPBadGateway(text=f"{type(exc).__name__}: {exc}") from exc
            candle_cache[timeframe] = (time.time(), rows)
        response = web.json_response({
            "venue": "Binance",
            "market": "USDT perpetual",
            "symbol": "BTC/USDT:USDT",
            "timeframe": timeframe,
            "candles": [
                {"time": int(row[0] / 1000), "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]}
                for row in rows
            ],
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "no-store"
        return response

    async def close_exchange(_: web.Application) -> None:
        await exchange.close()

    app.router.add_get("/api/profile", profile)
    app.router.add_get("/api/candles", candles)
    app.router.add_get("/api/health", health)
    app.on_cleanup.append(close_exchange)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="crypto_collector/config.json")
    args = parser.parse_args()
    cfg = load_config(args.config)
    web.run_app(create_app(cfg), host=cfg.get("api_host", "127.0.0.1"), port=cfg.get("api_port", 8765))
