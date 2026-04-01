from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class DeliveryResult:
    success: bool
    external_msg_id: str | None = None
    error: str | None = None


class AbstractChannel(ABC):
    channel_type: str  # class constant

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    async def send(self, formatted_message: Any) -> DeliveryResult: ...

    @abstractmethod
    async def send_test(self) -> DeliveryResult: ...

    @abstractmethod
    async def health_check(self) -> DeliveryResult: ...
