import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.webhook_cog import WebhookCog

@pytest.mark.asyncio
async def test_send_to_webhook():
    bot = MagicMock()
    cog = WebhookCog(bot)
    cog.send_to_webhook = AsyncMock(return_value=True)
    result = await cog.send_to_webhook("http://example.com/webhook", "Test content")
    assert result is True

@pytest.mark.asyncio
async def test_broadcast_to_webhooks():
    bot = MagicMock()
    cog = WebhookCog(bot)
    cog.broadcast_to_webhooks = AsyncMock(return_value=True)
    result = await cog.broadcast_to_webhooks("Broadcast content")
    assert result is True
