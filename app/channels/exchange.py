"""
Exchange execution channel.

Receives an order specification dict from
:class:`~app.formatters.exchange.ExchangeFormatter` and places a real
(or testnet / dry-run) order on a crypto exchange via ccxt.

Config is validated on construction via
:class:`~app.types.channel_config.ExchangeChannelConfig` — any missing
required field or wrong type raises ``ValidationError`` before the first
network call.

See :class:`~app.types.channel_config.ExchangeChannelConfig` for the full
list of supported config keys and their documentation.
"""
from __future__ import annotations

from datetime import UTC
from typing import Any, NamedTuple

import structlog

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry
from app.config import get_settings
from app.integrations.exchange_factory import build_execution_client
from app.types.channel_config import ExchangeChannelConfig

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class _BalanceInfo(NamedTuple):
    """Resolved balance and price data for a single symbol."""

    free: float
    total: float
    price: float
    margin_currency: str
    base: str


async def _fetch_open_positions(client: Any, symbol: str) -> list[dict[str, Any]]:
    """Return open positions for *symbol* with a non-zero contract size."""
    try:
        positions = await client.fetch_positions([symbol])
        return [p for p in positions if float(p.get("contracts") or 0) != 0]
    except Exception:  # noqa: BLE001
        return []


def _resolve_symbol(symbol: str, markets: dict[str, Any]) -> str | None:
    """Map a generic symbol (e.g. ``ETH/USD``) to an exchange-native ccxt key.

    Resolution order:
    1. Exact match (spot, e.g. ``ETH/USDT``)
    2. Inverse perpetual (e.g. ``ETH/USD:ETH`` — Deribit)
    3. Linear USDT perpetual (e.g. ``ETH/USDT:USDT``)
    4. Linear USDC perpetual (e.g. ``ETH/USDC:USDC``)
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


def _in_trading_window(cfg: ExchangeChannelConfig) -> bool:
    """Return ``True`` if the current local time is within the configured window."""
    from datetime import datetime

    if cfg.trading_hours is None and not cfg.trading_days:
        return True

    try:
        from zoneinfo import ZoneInfo
        tz_name = cfg.trading_hours.timezone if cfg.trading_hours else "UTC"
        now = datetime.now(UTC).astimezone(ZoneInfo(tz_name))
    except Exception:  # noqa: BLE001
        now = datetime.now(UTC)  # type: ignore[assignment]

    if cfg.trading_days:
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if day_names[now.weekday()] not in cfg.trading_days:
            return False

    if cfg.trading_hours:
        def _hhmm_to_minutes(t: str) -> int:
            h, m = t.split(":")
            return int(h) * 60 + int(m)

        start = _hhmm_to_minutes(cfg.trading_hours.start)
        end = _hhmm_to_minutes(cfg.trading_hours.end)
        now_m = now.hour * 60 + now.minute
        if start <= end:
            return start <= now_m < end
        return now_m >= start or now_m < end  # overnight window

    return True


# ---------------------------------------------------------------------------
# ExchangeChannel
# ---------------------------------------------------------------------------


@ChannelRegistry.register("exchange")
class ExchangeChannel(AbstractChannel):
    """Places live (or dry-run) orders on a crypto exchange via ccxt."""

    channel_type = "exchange"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.cfg = ExchangeChannelConfig.model_validate(config)

    def _build_client(self) -> Any:
        return build_execution_client(
            exchange_id=self.cfg.exchange_id,
            api_key=self.cfg.api_key,
            api_secret=self.cfg.api_secret,
            testnet=self.cfg.testnet,
            passphrase=self.cfg.passphrase,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def send(self, formatted_message: dict[str, Any]) -> DeliveryResult:
        if not formatted_message or formatted_message.get("_test"):
            return await self.send_test()

        symbol: str = formatted_message["symbol"]
        side: str = formatted_message["side"]
        trade_type: str = formatted_message.get("trade_type", "spot")
        signal_value: int = int(formatted_message.get("signal_value", 0))
        confidence: float = float(formatted_message.get("confidence") or 1.0)

        # Pre-exchange gating — no network call needed
        gating_result = self._apply_gating(signal_value, side)
        if gating_result is not None:
            return gating_result

        client = self._build_client()
        try:
            return await self._execute(client, symbol, side, trade_type, confidence)
        except Exception as exc:  # noqa: BLE001
            log.warning("exchange_channel.order_failed",
                        exchange=self.cfg.exchange_id, symbol=symbol, error=str(exc))
            return DeliveryResult(success=False, error=str(exc))
        finally:
            await client.close()

    async def send_test(self) -> DeliveryResult:
        """Verify credentials by fetching account balance — no order placed."""
        client = self._build_client()
        try:
            await client.load_markets()
            balance = await client.fetch_balance()
            non_zero = {
                k: v for k, v in (balance.get("total") or {}).items()
                if v and float(v) > 0
            }
            log.info("exchange_channel.test_ok",
                     exchange=self.cfg.exchange_id, balances=non_zero)
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

    # ------------------------------------------------------------------
    # Private — trade gating (no exchange call)
    # ------------------------------------------------------------------

    def _apply_gating(self, signal_value: int, side: str) -> DeliveryResult | None:
        """Return a ``DeliveryResult`` to short-circuit, or ``None`` to proceed."""
        cfg = self.cfg

        if not cfg.trading_enabled:
            log.info("exchange_channel.trading_disabled", exchange=cfg.exchange_id)
            return DeliveryResult(success=True, external_msg_id="trading_disabled")

        if cfg.dry_run:
            log.info("exchange_channel.dry_run",
                     exchange=cfg.exchange_id, side=side, signal_value=signal_value)
            return DeliveryResult(success=True, external_msg_id="dry_run")

        if cfg.direction_filter == "long_only" and side != "buy":
            return DeliveryResult(success=True, external_msg_id="direction_filtered")
        if cfg.direction_filter == "short_only" and side != "sell":
            return DeliveryResult(success=True, external_msg_id="direction_filtered")

        if cfg.signal_strength_filter and signal_value not in cfg.signal_strength_filter:
            return DeliveryResult(success=True, external_msg_id="strength_filtered")

        if not _in_trading_window(cfg):
            return DeliveryResult(
                success=False, error="Outside configured trading hours/days"
            )

        return None

    # ------------------------------------------------------------------
    # Private — main execution flow
    # ------------------------------------------------------------------

    async def _execute(
        self,
        client: Any,
        symbol: str,
        side: str,
        trade_type: str,
        confidence: float,
    ) -> DeliveryResult:
        cfg = self.cfg

        # 1. Load markets and resolve symbol
        await client.load_markets()
        symbol = self._resolve_or_fail(symbol, client.markets)

        # 2. Set leverage for futures
        if trade_type == "futures" and cfg.leverage > 1:
            try:
                await client.set_leverage(cfg.leverage, symbol)
            except Exception:  # noqa: BLE001
                pass

        # 3. Close opposing position if configured
        if cfg.close_on_opposite_signal:
            await self._close_opposing(client, symbol, side)

        # 4. Guard max open positions
        open_positions = await _fetch_open_positions(client, symbol)
        guard = self._check_max_positions(open_positions, symbol)
        if guard is not None:
            return guard

        # 5. Fetch balance and price
        balance_info = await self._fetch_balance_and_price(client, symbol)

        # 6. Compute trade amount
        amount = self._compute_amount(balance_info, confidence)
        amount = float(client.amount_to_precision(symbol, amount))

        # 7. Check exposure limits
        all_positions = await _fetch_open_positions(client, symbol)
        exposure_result = self._check_exposure(all_positions, balance_info, amount, side, symbol)
        if exposure_result is not None:
            return exposure_result

        # 8. Place entry order
        order_id = await self._place_entry_order(client, symbol, side, amount, balance_info.price)

        # 9. Place risk management orders (non-blocking failures)
        await self._place_stop_loss(client, symbol, side, amount, balance_info.price, balance_info.margin_currency)
        await self._place_take_profit(client, symbol, side, amount, balance_info.price)

        log.info("exchange_channel.order_placed",
                 exchange=cfg.exchange_id, order_id=order_id, symbol=symbol, side=side)
        return DeliveryResult(success=True, external_msg_id=order_id)

    def _resolve_or_fail(self, symbol: str, markets: dict[str, Any]) -> str:
        resolved = _resolve_symbol(symbol, markets)
        if resolved is None:
            raise ValueError(f"No market for {symbol} on {self.cfg.exchange_id}")
        return resolved

    async def _close_opposing(self, client: Any, symbol: str, side: str) -> None:
        """Close any open position in the direction opposing *side*."""
        for pos in await _fetch_open_positions(client, symbol):
            pos_side = (pos.get("side") or "").lower()
            is_opposing = (side == "buy" and pos_side == "short") or (
                side == "sell" and pos_side == "long"
            )
            if not is_opposing:
                continue
            close_amount = abs(float(pos.get("contracts") or 0))
            if close_amount <= 0:
                continue
            close_side = "buy" if pos_side == "short" else "sell"
            try:
                await client.create_order(
                    symbol, "market", close_side, close_amount,
                    params={"reduceOnly": True},
                )
                log.info("exchange_channel.position_closed",
                         exchange=self.cfg.exchange_id, symbol=symbol,
                         closed_side=pos_side, amount=close_amount)
            except Exception as exc:  # noqa: BLE001
                log.warning("exchange_channel.position_close_failed", error=str(exc))

    def _check_max_positions(
        self, open_positions: list[dict[str, Any]], symbol: str
    ) -> DeliveryResult | None:
        if len(open_positions) >= self.cfg.max_open_positions:
            return DeliveryResult(
                success=False,
                error=f"Max open positions ({self.cfg.max_open_positions}) reached for {symbol}",
            )
        return None

    async def _fetch_balance_and_price(self, client: Any, symbol: str) -> _BalanceInfo:
        """Fetch free/total balance and current price.  Handles inverse contracts."""
        balance = await client.fetch_balance()
        free_map: dict[str, Any] = balance.get("free") or {}
        total_map: dict[str, Any] = balance.get("total") or {}

        base = symbol.split("/")[0]
        quote = symbol.split("/")[1].split(":")[0] if "/" in symbol else "USDT"
        margin_currency = self.cfg.quote_currency or quote

        free = float(free_map.get(margin_currency, 0))
        if free <= 0 and margin_currency == quote:
            # Fallback: inverse contracts hold margin in base currency
            margin_currency = base
            free = float(free_map.get(margin_currency, 0))

        if free <= 0:
            raise ValueError(
                f"No free {margin_currency} balance on {self.cfg.exchange_id}"
            )

        total = float(total_map.get(margin_currency) or free)

        ticker = await client.fetch_ticker(symbol)
        price = float(ticker.get("last") or ticker.get("close") or 0)
        if price <= 0:
            raise ValueError(f"Could not determine price for {symbol}")

        slippage_tol = self.cfg.slippage_tolerance_pct
        if slippage_tol:
            ask = float(ticker.get("ask") or price)
            bid = float(ticker.get("bid") or price)
            spread_pct = (ask - bid) / price
            if spread_pct > slippage_tol:
                raise ValueError(
                    f"Spread {spread_pct:.4%} exceeds slippage_tolerance {slippage_tol:.4%}"
                )

        return _BalanceInfo(
            free=free, total=total, price=price,
            margin_currency=margin_currency, base=base,
        )

    def _compute_amount(self, bi: _BalanceInfo, confidence: float) -> float:
        """Compute raw trade amount before precision rounding."""
        cfg = self.cfg

        if cfg.position_size_fixed is not None:
            amount = cfg.position_size_fixed
        else:
            s = get_settings()
            size_pct = cfg.position_size_pct or s.default_position_size_pct
            if cfg.confidence_scaling:
                size_pct *= confidence
            notional = bi.free * size_pct
            amount = notional if bi.margin_currency == bi.base else notional / bi.price

        if cfg.max_position_size_pct:
            cap = (
                bi.free * cfg.max_position_size_pct
                if bi.margin_currency == bi.base
                else bi.free * cfg.max_position_size_pct / bi.price
            )
            amount = min(amount, cap)

        if cfg.max_position_size_fixed:
            amount = min(amount, cfg.max_position_size_fixed)

        return amount

    def _check_exposure(
        self,
        all_positions: list[dict[str, Any]],
        bi: _BalanceInfo,
        amount: float,
        side: str,
        symbol: str,
    ) -> DeliveryResult | None:
        """Return a blocking ``DeliveryResult`` if any exposure limit would be breached."""
        cfg = self.cfg
        if bi.total <= 0:
            return None

        def _notional(pos: dict[str, Any]) -> float:
            return abs(
                float(pos.get("notional") or float(pos.get("contracts") or 0) * bi.price)
            )

        new_notional = amount if bi.margin_currency == bi.base else amount * bi.price

        if cfg.max_total_exposure_pct:
            total_notional = sum(_notional(p) for p in all_positions)
            if (total_notional + new_notional) / bi.total > cfg.max_total_exposure_pct:
                return DeliveryResult(
                    success=False,
                    error=f"max_total_exposure_pct ({cfg.max_total_exposure_pct:.0%}) would be breached",
                )

        if cfg.max_exposure_per_asset_pct:
            asset_notional = sum(
                _notional(p) for p in all_positions if p.get("symbol") == symbol
            )
            if (asset_notional + new_notional) / bi.total > cfg.max_exposure_per_asset_pct:
                return DeliveryResult(
                    success=False,
                    error=f"max_exposure_per_asset_pct ({cfg.max_exposure_per_asset_pct:.0%}) breached for {symbol}",
                )

        if cfg.max_exposure_per_direction_pct:
            net = sum(
                _notional(p) * (1 if (p.get("side") or "").lower() == "long" else -1)
                for p in all_positions
            )
            signed_new = new_notional * (1 if side == "buy" else -1)
            if abs(net + signed_new) / bi.total > cfg.max_exposure_per_direction_pct:
                return DeliveryResult(
                    success=False,
                    error=f"max_exposure_per_direction_pct ({cfg.max_exposure_per_direction_pct:.0%}) would be breached",
                )

        return None

    async def _place_entry_order(
        self, client: Any, symbol: str, side: str, amount: float, price: float
    ) -> str:
        """Place the entry order and return the exchange order ID."""
        cfg = self.cfg
        price_param: float | None = None
        if cfg.order_type == "limit":
            offset = cfg.limit_order_offset_pct
            raw = price * (1 - offset) if side == "buy" else price * (1 + offset)
            price_param = float(client.price_to_precision(symbol, raw))

        log.info("exchange_channel.placing_order",
                 exchange=cfg.exchange_id, symbol=symbol, side=side,
                 order_type=cfg.order_type, amount=amount, price=price)

        order = await client.create_order(
            symbol, cfg.order_type, side, amount, price=price_param
        )
        return str(order.get("id", ""))

    async def _place_stop_loss(
        self, client: Any, symbol: str, side: str, amount: float, price: float,
        margin_currency: str = "",
    ) -> None:
        """Attempt to place a stop-loss order.  Logs and continues on failure."""
        cfg = self.cfg
        sl_side = "sell" if side == "buy" else "buy"

        if cfg.trailing_stop_pct and not cfg.stop_loss_pct and not cfg.stop_loss_fixed:
            try:
                await client.create_order(
                    symbol, "trailing_stop_market", sl_side, amount,
                    params={"callbackRate": cfg.trailing_stop_pct * 100},
                )
                log.info("exchange_channel.trailing_stop_placed",
                         exchange=cfg.exchange_id, symbol=symbol,
                         trailing_pct=cfg.trailing_stop_pct)
            except Exception as exc:  # noqa: BLE001
                log.warning("exchange_channel.trailing_stop_failed", error=str(exc))
            return

        if not cfg.stop_loss_pct and not cfg.stop_loss_fixed:
            return

        if cfg.stop_loss_fixed:
            base = symbol.split("/")[0]
            loss_units = (
                cfg.stop_loss_fixed if margin_currency == base
                else cfg.stop_loss_fixed / price
            )
            pct = loss_units / amount if amount else 0.0
        else:
            pct = cfg.stop_loss_pct or 0.0

        sl_price = price * (1 - pct) if side == "buy" else price * (1 + pct)
        sl_price = float(client.price_to_precision(symbol, sl_price))

        try:
            await client.create_order(
                symbol, "stop_market", sl_side, amount,
                params={"stopPrice": sl_price},
            )
            log.info("exchange_channel.stop_loss_placed",
                     exchange=cfg.exchange_id, symbol=symbol, stop_price=sl_price)
        except Exception as exc:  # noqa: BLE001
            log.warning("exchange_channel.stop_loss_failed", error=str(exc))

    async def _place_take_profit(
        self, client: Any, symbol: str, side: str, amount: float, price: float
    ) -> None:
        """Attempt to place take-profit order(s).  Logs and continues on failure."""
        cfg = self.cfg
        tp_side = "sell" if side == "buy" else "buy"

        if cfg.take_profit_levels:
            for level in cfg.take_profit_levels:
                tp_price = (
                    price * (1 + level.pct) if side == "buy"
                    else price * (1 - level.pct)
                )
                tp_price = float(client.price_to_precision(symbol, tp_price))
                tp_amount = float(client.amount_to_precision(symbol, amount * level.close_ratio))
                try:
                    await client.create_order(
                        symbol, "limit", tp_side, tp_amount,
                        price=tp_price, params={"reduceOnly": True},
                    )
                    log.info("exchange_channel.take_profit_placed",
                             exchange=cfg.exchange_id, symbol=symbol,
                             tp_price=tp_price, close_ratio=level.close_ratio)
                except Exception as exc:  # noqa: BLE001
                    log.warning("exchange_channel.take_profit_failed", error=str(exc))
            return

        if not cfg.take_profit_pct and not cfg.take_profit_fixed:
            return

        if cfg.take_profit_fixed:
            pct = cfg.take_profit_fixed / (amount * price) if amount and price else 0.0
        else:
            pct = cfg.take_profit_pct or 0.0

        tp_price = price * (1 + pct) if side == "buy" else price * (1 - pct)
        tp_price = float(client.price_to_precision(symbol, tp_price))

        try:
            await client.create_order(
                symbol, "limit", tp_side, amount,
                price=tp_price, params={"reduceOnly": True},
            )
            log.info("exchange_channel.take_profit_placed",
                     exchange=cfg.exchange_id, symbol=symbol, tp_price=tp_price)
        except Exception as exc:  # noqa: BLE001
            log.warning("exchange_channel.take_profit_failed", error=str(exc))

