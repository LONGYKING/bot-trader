# Import all channel modules to trigger @ChannelRegistry.register() decorators.
from app.channels import discord, email, exchange, slack, telegram, webhook, whatsapp

__all__ = ["discord", "email", "exchange", "slack", "telegram", "webhook", "whatsapp"]
