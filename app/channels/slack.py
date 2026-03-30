import ssl
from typing import Any

import aiohttp
import certifi

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())
_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


@ChannelRegistry.register("slack")
class SlackChannel(AbstractChannel):
    """Slack channel via Incoming Webhook or Bot Token + channel ID.

    Config keys (webhook takes priority if both are supplied):
        webhook_url (str, optional): Slack Incoming Webhook URL.
        bot_token (str, optional): Bot OAuth token (xoxb-...).
        channel_id (str, optional): Channel/conversation ID (required with bot_token).
    """

    channel_type = "slack"

    def _use_webhook(self) -> bool:
        return bool(self.config.get("webhook_url"))

    async def send(self, formatted_message: dict[str, Any]) -> DeliveryResult:
        if self._use_webhook():
            return await self._send_via_webhook(formatted_message)
        return await self._send_via_api(formatted_message)

    async def _send_via_webhook(self, payload: dict) -> DeliveryResult:
        url: str = self.config["webhook_url"]
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.post(url, json=payload) as resp:
                    body = await resp.text()
                    if resp.status == 200 and body.strip() == "ok":
                        return DeliveryResult(success=True)
                    return DeliveryResult(
                        success=False,
                        error=f"HTTP {resp.status}: {body}",
                    )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def _send_via_api(self, payload: dict) -> DeliveryResult:
        bot_token: str = self.config["bot_token"]
        channel_id: str = self.config["channel_id"]
        body = {**payload, "channel": channel_id}
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.post(
                    _POST_MESSAGE_URL, json=body, headers=headers
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("ok"):
                        ts = data.get("ts")
                        return DeliveryResult(success=True, external_msg_id=ts)
                    error = data.get("error", f"HTTP {resp.status}")
                    return DeliveryResult(success=False, error=error)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.slack import SlackFormatter

        msg = SlackFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        if self._use_webhook():
            # Slack webhooks have no dedicated health endpoint; send a benign
            # ping payload and treat a 200 "ok" response as healthy.
            ping_payload = {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "_Bot Trader health check ping_ ✅",
                        },
                    }
                ]
            }
            return await self._send_via_webhook(ping_payload)

        # Bot-token path: use auth.test
        bot_token: str = self.config.get("bot_token", "")
        headers = {"Authorization": f"Bearer {bot_token}"}
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.get(
                    "https://slack.com/api/auth.test", headers=headers
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("ok"):
                        return DeliveryResult(success=True)
                    error = data.get("error", f"HTTP {resp.status}")
                    return DeliveryResult(success=False, error=error)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
