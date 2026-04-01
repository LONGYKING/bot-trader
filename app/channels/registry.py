
from app.channels.base import AbstractChannel


class ChannelRegistry:
    _registry: dict[str, type[AbstractChannel]] = {}

    @classmethod
    def register(cls, channel_type: str):
        def decorator(klass: type[AbstractChannel]) -> type[AbstractChannel]:
            cls._registry[channel_type] = klass
            return klass

        return decorator

    @classmethod
    def get(cls, channel_type: str) -> type[AbstractChannel]:
        if channel_type not in cls._registry:
            raise ValueError(
                f"Channel type '{channel_type}' not registered. "
                f"Available: {list(cls._registry)}"
            )
        return cls._registry[channel_type]

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._registry.keys())

    @classmethod
    def instantiate(cls, channel_type: str, config: dict) -> AbstractChannel:
        return cls.get(channel_type)(config)
