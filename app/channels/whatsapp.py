import aiohttp

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry

_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _whatsapp_number(number: str) -> str:
    """Ensure a number is prefixed with 'whatsapp:'."""
    if not number.startswith("whatsapp:"):
        return f"whatsapp:{number}"
    return number


@ChannelRegistry.register("whatsapp")
class WhatsAppChannel(AbstractChannel):
    """WhatsApp channel via Twilio REST API (aiohttp, no SDK).

    Required config keys:
        account_sid (str): Twilio Account SID.
        auth_token (str): Twilio Auth Token.
        from_number (str): Twilio WhatsApp-enabled number, e.g. "+14155238886".
        to_number (str): Recipient WhatsApp number, e.g. "+447700900001".
    """

    channel_type = "whatsapp"

    def _messages_url(self) -> str:
        return (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.config['account_sid']}/Messages.json"
        )

    async def send(self, formatted_message: str) -> DeliveryResult:
        url = self._messages_url()
        form_data = aiohttp.FormData()
        form_data.add_field("From", _whatsapp_number(self.config["from_number"]))
        form_data.add_field("To", _whatsapp_number(self.config["to_number"]))
        form_data.add_field("Body", formatted_message)

        auth = aiohttp.BasicAuth(
            login=self.config["account_sid"],
            password=self.config["auth_token"],
        )
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post(url, data=form_data, auth=auth) as resp:
                    data = await resp.json()
                    if resp.status in (200, 201):
                        sid: str | None = data.get("sid")
                        return DeliveryResult(success=True, external_msg_id=sid)
                    error_msg = data.get(
                        "message", data.get("code", f"HTTP {resp.status}")
                    )
                    return DeliveryResult(success=False, error=str(error_msg))
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.whatsapp import WhatsAppFormatter

        msg = WhatsAppFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        # Fetch account info — a 200 response confirms credentials are valid.
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.config['account_sid']}.json"
        )
        auth = aiohttp.BasicAuth(
            login=self.config["account_sid"],
            password=self.config["auth_token"],
        )
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(url, auth=auth) as resp:
                    if resp.status == 200:
                        return DeliveryResult(success=True)
                    data = await resp.json()
                    error_msg = data.get("message", f"HTTP {resp.status}")
                    return DeliveryResult(success=False, error=str(error_msg))
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
