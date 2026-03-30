import ssl
from typing import Any

import aiohttp
import certifi

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


@ChannelRegistry.register("discord")
class DiscordChannel(AbstractChannel):
    """Discord channel via Webhook URL.

    Required config keys:
        webhook_url (str): Discord Webhook URL.
    """

    channel_type = "discord"

    async def send(self, formatted_message: dict[str, Any]) -> DeliveryResult:
        url: str = self.config["webhook_url"]
        # Append ?wait=true so Discord returns the message object (HTTP 200)
        # instead of the default 204 with empty body.
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.post(
                    url, json=formatted_message, params={"wait": "true"}
                ) as resp:
                    # 200 with body when ?wait=true; 204 when not using wait
                    if resp.status in (200, 204):
                        msg_id: str | None = None
                        if resp.status == 200:
                            try:
                                data = await resp.json()
                                msg_id = str(data.get("id")) if data.get("id") else None
                            except Exception:  # noqa: BLE001
                                pass
                        return DeliveryResult(success=True, external_msg_id=msg_id)
                    body = await resp.text()
                    return DeliveryResult(
                        success=False, error=f"HTTP {resp.status}: {body}"
                    )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.discord import DiscordFormatter

        msg = DiscordFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        # GET the webhook URL — Discord returns metadata (200) if the token is valid.
        url: str = self.config["webhook_url"]
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return DeliveryResult(success=True)
                    body = await resp.text()
                    return DeliveryResult(
                        success=False, error=f"HTTP {resp.status}: {body}"
                    )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
