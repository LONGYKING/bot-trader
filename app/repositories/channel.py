import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, update

from app.config import get_settings
from app.models.channel import Channel
from app.repositories.base import BaseRepository


def _derive_key() -> bytes:
    settings = get_settings()
    return hashlib.sha256(settings.secret_key.encode()).digest()


class ChannelRepository(BaseRepository[Channel]):
    model = Channel

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _encrypt_config(self, config: dict) -> dict:
        """Encrypt a config dict using AES-256-GCM.

        Returns a dict of the form::

            {"data": "<base64(nonce + ciphertext)>"}
        """
        key = _derive_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(config, separators=(",", ":")).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        encoded = base64.b64encode(nonce + ciphertext).decode()
        return {"data": encoded}

    def _decrypt_config(self, stored: dict) -> dict:
        """Decrypt a config dict that was produced by :meth:`_encrypt_config`."""
        key = _derive_key()
        aesgcm = AESGCM(key)
        raw = base64.b64decode(stored["data"])
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    async def create(self, data: dict[str, Any]) -> Channel:
        if "config" in data and isinstance(data["config"], dict):
            # Only encrypt if it does not already look like an envelope
            if "data" not in data["config"]:
                data = {**data, "config": self._encrypt_config(data["config"])}
        return await super().create(data)

    async def get_by_id(self, id: uuid.UUID) -> Channel | None:
        instance = await super().get_by_id(id)
        if instance is not None and isinstance(instance.config, dict):
            if "data" in instance.config:
                instance.config = self._decrypt_config(instance.config)
        return instance

    async def update(self, id: uuid.UUID, data: dict[str, Any]) -> Channel | None:
        if "config" in data and isinstance(data["config"], dict):
            if "data" not in data["config"]:
                data = {**data, "config": self._encrypt_config(data["config"])}
        return await super().update(id, data)

    # ------------------------------------------------------------------
    # Additional queries
    # ------------------------------------------------------------------

    async def list_active(self) -> list[Channel]:
        stmt = (
            select(Channel)
            .where(Channel.is_active == True)  # noqa: E712
            .order_by(Channel.name)
        )
        result = await self.session.execute(stmt)
        channels = list(result.scalars().all())
        for ch in channels:
            if isinstance(ch.config, dict) and "data" in ch.config:
                ch.config = self._decrypt_config(ch.config)
        return channels

    async def get_by_name(self, name: str) -> Channel | None:
        stmt = select(Channel).where(Channel.name == name)
        result = await self.session.execute(stmt)
        channel = result.scalar_one_or_none()
        if channel is not None and isinstance(channel.config, dict):
            if "data" in channel.config:
                channel.config = self._decrypt_config(channel.config)
        return channel

    async def update_health(self, id: uuid.UUID, ok: bool) -> None:
        stmt = (
            update(Channel)
            .where(Channel.id == id)
            .values(
                last_health_at=datetime.now(timezone.utc),
                last_health_ok=ok,
            )
        )
        await self.session.execute(stmt)
