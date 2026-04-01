"""
Async OHLCV fetcher with 3-provider fallback chain.

Provider priority:
  1. Binance  — direct aiohttp REST (api.binance.com/api/v3/klines), no ccxt/load_markets
  2. Deribit  — direct aiohttp, free public REST (perpetual futures price)
  3. Bitfinex — direct aiohttp, free public REST (spot USD pair)

Public API:
  - fetch_ohlcv(exchange_id, symbol, timeframe, limit, since)
  - fetch_ohlcv_range(exchange_id, symbol, timeframe, date_from, date_to)

``exchange_id`` selects the *preferred* provider but all three are always
tried in order on any failure.
"""
from __future__ import annotations

import asyncio
import ssl
from datetime import UTC, datetime

import aiohttp
import certifi
import pandas as pd
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20)

_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
_BINANCE_TF: dict[str, str] = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
    "1d": "1d", "3d": "3d", "1w": "1w",
}

# SSL context using certifi's CA bundle — fixes macOS / Docker SSL cert errors
# for both our direct aiohttp calls and ccxt's internal aiohttp session.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Transient network errors worth retrying — excludes HTTP 4xx (bad symbol, etc.)
_TRANSIENT = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerTimeoutError,
    aiohttp.ServerDisconnectedError,
    asyncio.TimeoutError,
    TimeoutError,
)


async def _call_with_retry(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Call ``fn(*args, **kwargs)`` with up to 3 attempts on transient network errors."""
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    ):
        with attempt:
            return await fn(*args, **kwargs)

# ---------------------------------------------------------------------------
# Timeframe mappings per provider
# ---------------------------------------------------------------------------

_DERIBIT_TF: dict[str, str] = {
    "1m": "1", "3m": "3", "5m": "5", "10m": "10", "15m": "15",
    "30m": "30", "1h": "60", "2h": "120", "3h": "180", "4h": "240",
    "6h": "360", "12h": "720", "1d": "1D",
}

_BITFINEX_TF: dict[str, str] = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "3h": "3h", "4h": "4h", "6h": "6h",
    "12h": "12h", "1d": "1D", "1w": "7D",
}


# ---------------------------------------------------------------------------
# Symbol normalisation helpers
# ---------------------------------------------------------------------------

def _deribit_instrument(symbol: str) -> str:
    """BTC/USDT  →  BTC-PERPETUAL"""
    base = symbol.split("/")[0].upper()
    return f"{base}-PERPETUAL"


def _deribit_instrument_usdc(symbol: str) -> str:
    """BTC/USDT  →  BTC_USDC-PERPETUAL  (new Deribit naming for non-BTC assets)"""
    base = symbol.split("/")[0].upper()
    return f"{base}_USDC-PERPETUAL"


def _binance_rest_symbol(symbol: str) -> str:
    """BTC/USDT → BTCUSDT, ETH/USD → ETHUSDT (Binance REST format, USDT pairs only)"""
    base, quote = symbol.split("/") if "/" in symbol else (symbol, "USDT")
    quote = quote.upper()
    if quote == "USD":
        quote = "USDT"
    return base.upper() + quote


def _bitfinex_symbol(symbol: str) -> str:
    """BTC/USDT  →  BTCUSD   (Bitfinex uses USD, not USDT)"""
    base = symbol.split("/")[0].upper()
    return f"{base}USD"


# ---------------------------------------------------------------------------
# Private provider fetchers — each returns [[ts_ms, o, h, l, c, v], ...]
# ---------------------------------------------------------------------------

def _parse_binance_klines(data: list) -> list[list]:
    """Binance klines: [openTime, open, high, low, close, volume, ...] → standard format."""
    return [
        [int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])]
        for row in data
    ]


async def _fetch_binance(
    symbol: str,
    timeframe: str,
    limit: int,
    since_ms: int | None,
) -> list[list]:
    """Direct Binance REST klines — no ccxt, no load_markets() overhead."""
    interval = _BINANCE_TF.get(timeframe)
    if interval is None:
        raise ValueError(f"Binance does not support timeframe {timeframe!r}")

    params: dict = {"symbol": _binance_rest_symbol(symbol), "interval": interval, "limit": min(limit, 1000)}
    if since_ms:
        params["startTime"] = since_ms

    connector = aiohttp.TCPConnector(ssl=_SSL_CTX)
    async with aiohttp.ClientSession(connector=connector, timeout=_HTTP_TIMEOUT) as session:
        async with session.get(_BINANCE_KLINES_URL, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return _parse_binance_klines(data)


async def _fetch_binance_range(
    symbol: str,
    timeframe: str,
    since_ms: int,
    end_ms: int,
    batch_size: int = 1000,
) -> list[list]:
    """Paginated Binance REST klines over a full date range."""
    interval = _BINANCE_TF.get(timeframe)
    if interval is None:
        raise ValueError(f"Binance does not support timeframe {timeframe!r}")

    rest_symbol = _binance_rest_symbol(symbol)
    all_bars: list[list] = []
    cursor = since_ms

    connector = aiohttp.TCPConnector(ssl=_SSL_CTX)
    async with aiohttp.ClientSession(connector=connector, timeout=_HTTP_TIMEOUT) as session:
        while True:
            params = {
                "symbol": rest_symbol, "interval": interval,
                "startTime": cursor, "endTime": end_ms, "limit": batch_size,
            }
            async with session.get(_BINANCE_KLINES_URL, params=params) as resp:  # type: ignore[arg-type]
                resp.raise_for_status()
                data = await resp.json()

            if not data:
                break
            bars = _parse_binance_klines(data)
            all_bars.extend(bars)
            last_ts = bars[-1][0]
            if last_ts >= end_ms or len(data) < batch_size:
                break
            cursor = last_ts + 1
            await asyncio.sleep(0.1)

    return all_bars


async def _fetch_deribit(
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
) -> list[list]:
    resolution = _DERIBIT_TF.get(timeframe)
    if resolution is None:
        raise ValueError(f"Deribit does not support timeframe {timeframe!r}")

    # Try legacy name first (e.g. BTC-PERPETUAL), then USDC variant (e.g. ETH_USDC-PERPETUAL)
    instruments = [_deribit_instrument(symbol), _deribit_instrument_usdc(symbol)]
    last_exc: Exception | None = None

    for instrument in instruments:
        url = (
            "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
            f"?instrument_name={instrument}"
            f"&resolution={resolution}"
            f"&start_timestamp={start_ms}"
            f"&end_timestamp={end_ms}"
        )

        try:
            connector = aiohttp.TCPConnector(ssl=_SSL_CTX)
            async with aiohttp.ClientSession(connector=connector, timeout=_HTTP_TIMEOUT) as session:
                async with session.get(url) as resp:
                    if resp.status == 400 and instrument == instruments[0]:
                        log.debug("deribit_legacy_name_400", instrument=instrument, symbol=symbol)
                        last_exc = aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=400
                        )
                        continue
                    resp.raise_for_status()
                    payload = await resp.json()
        except aiohttp.ClientResponseError as exc:
            if exc.status == 400 and instrument == instruments[0]:
                last_exc = exc
                continue
            raise

        if "error" in payload:
            raise RuntimeError(f"Deribit error: {payload['error']}")

        result = payload.get("result", {})
        if result.get("status") != "ok":
            raise RuntimeError(f"Deribit status not ok: {result}")

        ticks = result.get("ticks", [])
        if not ticks:
            return []

        # Deribit returns parallel arrays — zip into [[ts, o, h, l, c, v], ...]
        bars = [
            [t, o, h, l, c, v]
            for t, o, h, l, c, v in zip(
                ticks,
                result["open"],
                result["high"],
                result["low"],
                result["close"],
                result["volume"],
            )
        ]
        log.debug("deribit_fetch_ok", instrument=instrument, bars=len(bars))
        return bars

    raise last_exc or RuntimeError(f"Deribit: no valid instrument found for {symbol!r}")


async def _fetch_bitfinex(
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    limit: int = 1000,
) -> list[list]:
    resolution = _BITFINEX_TF.get(timeframe)
    if resolution is None:
        raise ValueError(f"Bitfinex does not support timeframe {timeframe!r}")

    bfx_symbol = _bitfinex_symbol(symbol)
    url = (
        f"https://api-pub.bitfinex.com/v2/candles/trade:{resolution}:t{bfx_symbol}/hist"
        f"?limit={limit}&start={start_ms}&end={end_ms}&sort=1"
    )

    connector = aiohttp.TCPConnector(ssl=_SSL_CTX)
    async with aiohttp.ClientSession(connector=connector, timeout=_HTTP_TIMEOUT) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected Bitfinex response: {data}")
    if data and data[0] == "error":
        raise RuntimeError(f"Bitfinex error: {data}")

    # Bitfinex format: [MTS, Open, Close, High, Low, Volume]  ← note Close before High
    # Reorder to standard [ts, open, high, low, close, volume]
    bars = [
        [row[0], row[1], row[3], row[4], row[2], row[5]]
        for row in data
        if isinstance(row, list) and len(row) >= 6
    ]
    return bars


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bars_to_df(raw: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=OHLCV_COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df.astype(
        {"open": float, "high": float, "low": float, "close": float, "volume": float}
    )
    df = df[~df.index.duplicated(keep="last")]
    df.sort_index(inplace=True)
    return df


def _ms_now() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def fetch_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    limit: int = 500,
    since: datetime | None = None,
) -> pd.DataFrame:
    """
    Fetch the latest ``limit`` OHLCV bars for ``symbol``.

    Tries Binance → Deribit → Bitfinex in order; uses the first that succeeds.
    ``exchange_id`` sets the preferred provider but all three are tried.

    Raises ValueError if all providers fail or return < 50 bars.
    """
    since_ms = _dt_to_ms(since) if since else None
    # For Deribit/Bitfinex we need a start_ms; approximate from limit + timeframe
    end_ms = _ms_now()
    tf_seconds = _timeframe_to_seconds(timeframe)
    approx_start_ms = end_ms - (limit * tf_seconds * 1000)

    errors: dict[str, str] = {}

    # Build ordered provider list — preferred first
    providers = _ordered_providers(exchange_id)

    for provider in providers:
        try:
            if provider == "binance":
                raw = await _call_with_retry(_fetch_binance, symbol, timeframe, limit, since_ms)
            elif provider == "deribit":
                raw = await _call_with_retry(_fetch_deribit, symbol, timeframe, approx_start_ms, end_ms)
                raw = raw[-limit:]  # trim to requested limit
            elif provider == "bitfinex":
                raw = await _call_with_retry(_fetch_bitfinex, symbol, timeframe, approx_start_ms, end_ms, limit)
            else:
                continue

            if len(raw) >= 50:
                log.debug("ohlcv_fetch_success", provider=provider, symbol=symbol, bars=len(raw))
                return _bars_to_df(raw)

            errors[provider] = f"only {len(raw)} bars returned"
            log.warning("ohlcv_insufficient_bars", provider=provider, symbol=symbol, bars=len(raw))

        except Exception as exc:
            errors[provider] = str(exc)
            log.warning("ohlcv_provider_failed", provider=provider, symbol=symbol, error=str(exc))

    raise ValueError(
        f"All OHLCV providers failed for {symbol!r} {timeframe!r}. "
        f"Errors: {errors}"
    )


async def fetch_ohlcv_range(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    date_from: datetime,
    date_to: datetime,
    batch_size: int = 500,
) -> pd.DataFrame:
    """
    Fetch OHLCV data over a full date range (used by the backtest engine).

    Tries Binance → Deribit → Bitfinex. Requires >= 200 bars.
    """
    start_ms = _dt_to_ms(date_from)
    end_ms = _dt_to_ms(date_to)

    errors: dict[str, str] = {}
    providers = _ordered_providers(exchange_id)

    for provider in providers:
        try:
            if provider == "binance":
                raw = await _call_with_retry(_fetch_binance_range, symbol, timeframe, start_ms, end_ms, batch_size)
            elif provider == "deribit":
                raw = await _call_with_retry(_fetch_deribit, symbol, timeframe, start_ms, end_ms)
            elif provider == "bitfinex":
                raw = await _call_with_retry(_fetch_bitfinex, symbol, timeframe, start_ms, end_ms, limit=10000)
            else:
                continue

            if not raw:
                errors[provider] = "no data returned"
                continue

            df = _bars_to_df(raw)
            # Trim to requested range — use tz_convert if already aware, tz_localize if naive
            end_ts = pd.Timestamp(date_to)
            if end_ts.tzinfo is None:
                end_ts = end_ts.tz_localize("UTC")
            df = df[df.index <= end_ts]

            if len(df) >= 50:
                log.debug("ohlcv_range_success", provider=provider, symbol=symbol, bars=len(df))
                return df

            errors[provider] = f"only {len(df)} bars (need 50 minimum)"
            log.warning("ohlcv_range_insufficient", provider=provider, symbol=symbol, bars=len(df))

        except Exception as exc:
            errors[provider] = str(exc)
            log.warning("ohlcv_range_provider_failed", provider=provider, symbol=symbol, error=str(exc))

    raise ValueError(
        f"All OHLCV providers failed for range fetch {symbol!r} {timeframe!r}. "
        f"Errors: {errors}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ordered_providers(preferred: str) -> list[str]:
    """Return [preferred, ...rest] deduplicated."""
    all_providers = ["binance", "deribit", "bitfinex"]
    if preferred in all_providers:
        rest = [p for p in all_providers if p != preferred]
        return [preferred] + rest
    return all_providers


def _timeframe_to_seconds(tf: str) -> int:
    """Convert timeframe string to seconds (approximate)."""
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    tf = tf.lower()
    for suffix, mult in units.items():
        if tf.endswith(suffix):
            try:
                return int(tf[:-1]) * mult
            except ValueError:
                pass
    return 3600  # default 1h
