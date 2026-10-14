"""Opt-in Discord and Telegram webhook delivery."""
from __future__ import annotations

import logging

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send(self, item: dict) -> None:
        text = f"[InfraPulse / {item['level'].upper()}] {item['message']}"
        async with httpx.AsyncClient(timeout=8) as client:
            if self.settings.discord_webhook_url:
                try:
                    resp = await client.post(self.settings.discord_webhook_url, json={"content": text})
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Discord notification failed: %s", type(exc).__name__)
            if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
                try:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage",
                        json={"chat_id": self.settings.telegram_chat_id, "text": text},
                    )
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Telegram notification failed: %s", type(exc).__name__)
