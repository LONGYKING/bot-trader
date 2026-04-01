from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib

from app.channels.base import AbstractChannel, DeliveryResult
from app.channels.registry import ChannelRegistry


@ChannelRegistry.register("email")
class EmailChannel(AbstractChannel):
    """Email channel via SMTP with STARTTLS (aiosmtplib).

    Required config keys:
        smtp_host (str): SMTP server hostname.
        smtp_port (int, default 587): SMTP port.
        smtp_user (str): SMTP authentication username.
        smtp_password (str): SMTP authentication password.
        from_email (str): Sender address.
        to_email (str | list[str]): Recipient address(es).
    """

    channel_type = "email"

    def _build_message(self, subject: str, html: str, text: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config["from_email"]
        to = self.config["to_email"]
        msg["To"] = ", ".join(to) if isinstance(to, list) else to

        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        return msg

    async def send(self, formatted_message: dict[str, Any]) -> DeliveryResult:
        subject: str = formatted_message["subject"]
        html: str = formatted_message["html"]
        text: str = formatted_message["text"]

        msg = self._build_message(subject, html, text)

        smtp_host: str = self.config["smtp_host"]
        smtp_port: int = int(self.config.get("smtp_port", 587))
        smtp_user: str = self.config["smtp_user"]
        smtp_password: str = self.config["smtp_password"]

        try:
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=True,
            )
            return DeliveryResult(success=True)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))

    async def send_test(self) -> DeliveryResult:
        from app.formatters.email import EmailFormatter

        msg = EmailFormatter().format_test()
        return await self.send(msg)

    async def health_check(self) -> DeliveryResult:
        smtp_host: str = self.config["smtp_host"]
        smtp_port: int = int(self.config.get("smtp_port", 587))
        smtp_user: str = self.config["smtp_user"]
        smtp_password: str = self.config["smtp_password"]

        try:
            client = aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                timeout=30,
            )
            await client.connect()
            await client.starttls()
            await client.login(smtp_user, smtp_password)
            await client.quit()
            return DeliveryResult(success=True)
        except Exception as exc:  # noqa: BLE001
            return DeliveryResult(success=False, error=str(exc))
