import ssl

import aiohttp
import certifi

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


@ChannelRegistry.register("telegram")
class TelegramChannel(AbstractChannel):
    """Telegram Bot API channel.

    Required config keys:
        bot_token (str): Telegram Bot API token.
        chat_id (str | int): Target chat / channel ID.
    """

    channel_type = "telegram"

    @property
    def _api_base(self) -> str:
        token = self.config["bot_token"]
        return f"https://api.telegram.org/bot{token}"

    async def send(self, formatted_message: str) -> DeliveryResult:
        url = f"{self._api_base}/sendMessage"
        payload = {
            "chat_id": self.config["chat_id"],
            "text": formatted_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    if resp.status != 200 or not data.get("ok"):
                        desc = data.get("description", f"HTTP {resp.status}")
                        return DeliveryResult(success=False, error=desc)
                    msg_id = str(data["result"]["message_id"])
                    return DeliveryResult(success=True, external_msg_id=msg_id)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.telegram import TelegramFormatter

        msg = TelegramFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        url = f"{self._api_base}/getMe"
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("ok"):
                        return DeliveryResult(success=True)
                    desc = data.get("description", f"HTTP {resp.status}")
                    return DeliveryResult(success=False, error=desc)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
