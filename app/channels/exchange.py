"""
Exchange execution channel.

Receives an order specification from ExchangeFormatter and places a real
(or testnet) order on a crypto exchange via ccxt.

Required config keys:
    exchange_id (str):        ccxt exchange name, e.g. "binance", "bybit", "okx"
    api_key (str):            Exchange API key
    api_secret (str):         Exchange API secret

Optional config keys:
    passphrase (str):         Required for OKX and some others
    position_size_pct (float): Fraction of available quote balance per trade (default 0.05)
    order_type (str):          "market" | "limit" (default "market")
    testnet (bool):            Connect to sandbox / paper trading (default False)
    stop_loss_pct (float):     If set, places a stop-market after entry (default None)
    leverage (int):            Futures leverage multiplier (default 1, spot-safe)

Delivery tracking:
    external_msg_id = exchange order ID (stored in signal_deliveries.external_msg_id)
"""
from __future__ import annotations

import structlog

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry
from app.integrations.exchange_factory import build_execution_client

log = structlog.get_logger(__name__)

_DEFAULT_POSITION_SIZE_PCT = 0.05
_DEFAULT_ORDER_TYPE = "market"


async def _get_open_positions(client, symbol: str) -> list[dict]:
    """Return open positions for *symbol* with non-zero size.

    Returns an empty list if the exchange does not support fetch_positions.
    """
    try:
        positions = await client.fetch_positions([symbol])
        return [p for p in positions if float(p.get("contracts") or 0) != 0]
    except Exception:  # noqa: BLE001 — exchange may not support positions API
        return []


def _resolve_symbol(symbol: str, markets: dict) -> str | None:
    """Map a generic symbol (e.g. ETH/USD) to an exchange-native ccxt key.

    Tries in order:
    1. Exact match — works for spot/linear (Binance, Bybit USDT-perps)
    2. Inverse perpetual: ETH/USD → ETH/USD:ETH  (Deribit, BitMEX)
    3. Linear USDT perp: ETH/USD → ETH/USDT:USDT
    4. Linear USDC perp: ETH/USD → ETH/USDC:USDC
    Returns None if no match found in the exchange's market list.
    """
    if symbol in markets:
        return symbol
    base = symbol.split("/")[0]
    for candidate in (
        f"{base}/USD:{base}",
        f"{base}/USDT:USDT",
        f"{base}/USDC:USDC",
    ):
        if candidate in markets:
            return candidate
    return None


@ChannelRegistry.register("exchange")
class ExchangeChannel(AbstractChannel):
    channel_type = "exchange"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client(self):
        cfg = self.config
        return build_execution_client(
            exchange_id=cfg["exchange_id"],
            api_key=cfg["api_key"],
            api_secret=cfg["api_secret"],
            testnet=bool(cfg.get("testnet", False)),
            passphrase=cfg.get("passphrase"),
        )

    def _position_size_pct(self) -> float:
        return float(self.config.get("position_size_pct", _DEFAULT_POSITION_SIZE_PCT))

    def _order_type(self) -> str:
        return str(self.config.get("order_type", _DEFAULT_ORDER_TYPE))

    def _stop_loss_pct(self) -> float | None:
        v = self.config.get("stop_loss_pct")
        return float(v) if v is not None else None

    def _take_profit_pct(self) -> float | None:
        v = self.config.get("take_profit_pct")
        return float(v) if v is not None else None

    def _close_on_opposite_signal(self) -> bool:
        return bool(self.config.get("close_on_opposite_signal", True))

    def _max_open_positions(self) -> int:
        return int(self.config.get("max_open_positions", 1))

    def _leverage(self) -> int:
        return int(self.config.get("leverage", 1))

    # ------------------------------------------------------------------
    # AbstractChannel interface  
    # ------------------------------------------------------------------

    async def send(self, formatted_message: dict) -> DeliveryResult:
        """Place an entry order on the exchange.

        formatted_message is produced by ExchangeFormatter.format_signal():
            {"symbol": "ETH/USDT", "side": "buy", "trade_type": "spot"}
        """
        if not formatted_message or formatted_message.get("_test"):
            return await self.send_test()

        symbol: str = formatted_message["symbol"]
        side: str = formatted_message["side"]
        trade_type: str = formatted_message.get("trade_type", "spot")
        order_type = self._order_type()
        exchange_id = self.config["exchange_id"]

        client = self._client()
        try:
            # 1. Load markets so ccxt knows precision / min order sizes
            await client.load_markets()

            # Resolve generic symbol (e.g. ETH/USD) to exchange-native key
            # (e.g. ETH/USD:ETH on Deribit inverse perpetuals)
            resolved = _resolve_symbol(symbol, client.markets)
            if resolved is None:
                return DeliveryResult(
                    success=False,
                    error=f"No market found for {symbol} on {exchange_id}",
                )
            symbol = resolved

            # 2. Set leverage for futures / perpetuals
            if trade_type == "futures" and self._leverage() > 1:
                try:
                    await client.set_leverage(self._leverage(), symbol)
                except Exception:  # noqa: BLE001
                    pass  # not all exchanges support this call the same way

            # 2b. Close any opposing position before opening a new one
            if self._close_on_opposite_signal():
                positions = await _get_open_positions(client, symbol)
                for pos in positions:
                    pos_side = (pos.get("side") or "").lower()  # "long" or "short"
                    is_opposing = (side == "buy" and pos_side == "short") or (
                        side == "sell" and pos_side == "long"
                    )
                    if is_opposing:
                        close_amount = abs(float(pos.get("contracts") or 0))
                        if close_amount > 0:
                            close_side = "buy" if pos_side == "short" else "sell"
                            try:
                                await client.create_order(
                                    symbol, "market", close_side, close_amount,
                                    params={"reduceOnly": True},
                                )
                                log.info(
                                    "exchange_channel.position_closed",
                                    exchange=exchange_id,
                                    symbol=symbol,
                                    closed_side=pos_side,
                                    amount=close_amount,
                                )
                            except Exception as close_err:  # noqa: BLE001
                                log.warning(
                                    "exchange_channel.position_close_failed",
                                    exchange=exchange_id,
                                    symbol=symbol,
                                    error=str(close_err),
                                )

            # 2c. Enforce max open positions limit
            open_positions = await _get_open_positions(client, symbol)
            if len(open_positions) >= self._max_open_positions():
                return DeliveryResult(
                    success=False,
                    error=(
                        f"Max open positions ({self._max_open_positions()}) "
                        f"already reached for {symbol} on {exchange_id}"
                    ),
                )

            # 3. Fetch available balance
            # Deribit and other inverse-contract exchanges hold margin in the
            # base currency (e.g. ETH for ETH/USD), not the quote. We honour
            # an explicit `quote_currency` config override first, then try the
            # quote, then fall back to the base.
            balance = await client.fetch_balance()
            free_map = balance.get("free", {})
            parts = symbol.split("/") if "/" in symbol else [symbol, "USDT"]
            base, quote = parts[0], parts[1]
            margin_currency = self.config.get("quote_currency") or quote

            free_quote = float(free_map.get(margin_currency, 0))
            if free_quote <= 0 and margin_currency == quote:
                # Inverse contract — try base currency (e.g. ETH on Deribit)
                margin_currency = base
                free_quote = float(free_map.get(margin_currency, 0))

            if free_quote <= 0:
                return DeliveryResult(
                    success=False,
                    error=f"No free {margin_currency} balance on {exchange_id}",
                )

            # 4. Compute order amount in base currency
            ticker = await client.fetch_ticker(symbol)
            price = float(ticker["last"] or ticker["close"])
            if price <= 0:
                return DeliveryResult(success=False, error=f"Bad price for {symbol}: {price}")

            # For inverse contracts the notional is in base currency; for
            # linear contracts it's in quote. In both cases `amount` is the
            # number of base units to buy/sell.
            notional = free_quote * self._position_size_pct()
            if margin_currency == base:
                # Inverse: notional already in base units
                amount = notional
            else:
                # Linear: convert quote notional to base units
                amount = notional / price
            amount = float(client.amount_to_precision(symbol, amount))

            log.info(
                "exchange_channel.placing_order",
                exchange=exchange_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
            )

            # 5. Place entry order
            order = await client.create_order(symbol, order_type, side, amount)
            order_id = str(order.get("id", ""))

            log.info(
                "exchange_channel.order_placed",
                exchange=exchange_id,
                order_id=order_id,
                symbol=symbol,
                side=side,
            )

            # 6. Optional stop-loss
            sl_pct = self._stop_loss_pct()
            if sl_pct and order_id:
                sl_side = "sell" if side == "buy" else "buy"
                sl_price = (
                    price * (1 - sl_pct) if side == "buy" else price * (1 + sl_pct)
                )
                sl_price = float(client.price_to_precision(symbol, sl_price))
                try:
                    await client.create_order(
                        symbol, "stop_market", sl_side, amount,
                        params={"stopPrice": sl_price},
                    )
                    log.info(
                        "exchange_channel.stop_loss_placed",
                        exchange=exchange_id,
                        symbol=symbol,
                        stop_price=sl_price,
                    )
                except Exception as sl_err:  # noqa: BLE001
                    log.warning(
                        "exchange_channel.stop_loss_failed",
                        error=str(sl_err),
                    )

            # 7. Optional take-profit (limit order on the opposite side)
            tp_pct = self._take_profit_pct()
            if tp_pct and order_id:
                tp_side = "sell" if side == "buy" else "buy"
                tp_price = (
                    price * (1 + tp_pct) if side == "buy" else price * (1 - tp_pct)
                )
                tp_price = float(client.price_to_precision(symbol, tp_price))
                try:
                    await client.create_order(
                        symbol, "limit", tp_side, amount,
                        price=tp_price,
                        params={"reduceOnly": True},
                    )
                    log.info(
                        "exchange_channel.take_profit_placed",
                        exchange=exchange_id,
                        symbol=symbol,
                        tp_price=tp_price,
                    )
                except Exception as tp_err:  # noqa: BLE001
                    log.warning(
                        "exchange_channel.take_profit_failed",
                        error=str(tp_err),
                    )

            return DeliveryResult(success=True, external_msg_id=order_id)

        except Exception as exc:  # noqa: BLE001
            log.warning(
                "exchange_channel.order_failed",
                exchange=exchange_id,
                symbol=symbol,
                error=str(exc),
            )
            return DeliveryResult(success=False, error=str(exc))
        finally:
            await client.close()

    async def send_test(self) -> DeliveryResult:
        """Verify credentials by fetching account balance (no order placed)."""
        exchange_id = self.config.get("exchange_id", "?")
        client = self._client()
        try:
            await client.load_markets()
            balance = await client.fetch_balance()
            total = balance.get("total", {})
            non_zero = {k: v for k, v in total.items() if v and float(v) > 0}
            log.info("exchange_channel.test_ok", exchange=exchange_id, balances=non_zero)
            return DeliveryResult(
                success=True,
                external_msg_id=f"balance_check:{list(non_zero.keys())[:3]}",
            )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
        finally:
            await client.close()

    async def health_check(self) -> DeliveryResult:
        return await self.send_test()
