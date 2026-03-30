import hashlib
import hmac
import json
import ssl
from typing import Any

import aiohttp
import certifi

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def _sign_payload(secret: str, body_bytes: bytes) -> str:
    """Return the HMAC-SHA256 hex digest prefixed with 'sha256='."""
    digest = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@ChannelRegistry.register("webhook")
class WebhookChannel(AbstractChannel):
    """Generic outbound Webhook channel.

    Required config keys:
        url (str): Target URL.

    Optional config keys:
        secret (str): If set, an HMAC-SHA256 signature is added as the
            X-Signature-SHA256 header.
        headers (dict[str, str]): Extra HTTP headers to include in every request.
    """

    channel_type = "webhook"

    async def send(self, formatted_message: dict[str, Any]) -> DeliveryResult:
        url: str = self.config["url"]
        secret: str | None = self.config.get("secret")
        extra_headers: dict = self.config.get("headers") or {}

        body_bytes = json.dumps(formatted_message, separators=(",", ":")).encode()

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **extra_headers,
        }
        if secret:
            headers["X-Signature-SHA256"] = _sign_payload(secret, body_bytes)

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.post(
                    url, data=body_bytes, headers=headers
                ) as resp:
                    if 200 <= resp.status < 300:
                        msg_id: str | None = resp.headers.get("X-Message-ID")
                        return DeliveryResult(success=True, external_msg_id=msg_id)
                    body_text = await resp.text()
                    return DeliveryResult(
                        success=False,
                        error=f"HTTP {resp.status}: {body_text}",
                    )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.webhook import WebhookFormatter

        msg = WebhookFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        # Send a minimal HEAD or GET request to the target URL to verify reachability.
        url: str = self.config["url"]
        extra_headers: dict = self.config.get("headers") or {}
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_SSL_CTX), timeout=_TIMEOUT) as session:
                async with session.head(url, headers=extra_headers) as resp:
                    # Any response (even 4xx) means the endpoint is reachable.
                    if resp.status < 500:
                        return DeliveryResult(success=True)
                    body_text = await resp.text()
                    return DeliveryResult(
                        success=False,
                        error=f"HTTP {resp.status}: {body_text}",
                    )
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
