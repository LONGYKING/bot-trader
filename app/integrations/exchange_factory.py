"""
ccxt async client factory with connection pooling per exchange_id.
"""
import asyncio
from typing import Any

import ccxt.async_support as ccxt

_clients: dict[str, Any] = {}
_lock = asyncio.Lock()

async def get_exchange_client(exchange_id: str, options: dict | None = None) -> Any:
    """
    Get or create a ccxt async exchange client.
    Clients are cached per exchange_id.
    """
    async with _lock:
        if exchange_id not in _clients:
            exchange_class = getattr(ccxt, exchange_id, None)
            if exchange_class is None:
                raise ValueError(f"Unknown exchange: {exchange_id}")
            config = {"enableRateLimit": True}
            if options:
                config.update(options)
            _clients[exchange_id] = exchange_class(config)
        return _clients[exchange_id]


def build_execution_client(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    testnet: bool = False,
    passphrase: str | None = None,
) -> Any:
    """
    Build a synchronous-style ccxt async client with user credentials.
    Used by ExchangeChannel for order execution (not cached — each channel
    has its own credentials).
    """
    exchange_class = getattr(ccxt, exchange_id, None)
    if exchange_class is None:
        raise ValueError(f"Unknown exchange: {exchange_id}")

    config: dict[str, Any] = {
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    }
    if passphrase:
        config["password"] = passphrase

    client = exchange_class(config)

    if testnet:
        client.set_sandbox_mode(True)

    return client


async def close_all_clients() -> None:
    """Close all cached exchange clients. Call on app shutdown."""
    async with _lock:
        for client in _clients.values():
            try:
                await client.close()
            except Exception:
                pass
        _clients.clear()
