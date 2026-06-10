import asyncio
import json
import logging
from typing import Callable

import requests
import websockets

logger = logging.getLogger(__name__)

EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"
HELIX_SUBS = "https://api.twitch.tv/helix/eventsub/subscriptions"
HELIX_USERS = "https://api.twitch.tv/helix/users"


def get_broadcaster_id(token: str, client_id: str, channel_name: str) -> str:
    resp = requests.get(
        HELIX_USERS,
        params={"login": channel_name},
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise ValueError(f"Channel '{channel_name}' not found on Twitch")
    return data[0]["id"]


def subscribe_to_redemptions(
    token: str, client_id: str, broadcaster_id: str, session_id: str
) -> None:
    resp = requests.post(
        HELIX_SUBS,
        json={
            "type": "channel.channel_points_custom_reward_redemption.add",
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
            "transport": {"method": "websocket", "session_id": session_id},
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Client-Id": client_id,
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    resp.raise_for_status()


class TwitchListener:
    def __init__(
        self,
        token: str,
        client_id: str,
        channel_name: str,
        reward_name: str,
        on_redemption: Callable[[str, str], None],
        on_status_change: Callable[[str], None],
    ):
        self.token = token
        self.client_id = client_id
        self.channel_name = channel_name
        self.reward_name = reward_name
        self.on_redemption = on_redemption
        self.on_status_change = on_status_change
        self._running = False

    async def run(self) -> None:
        self._running = True
        broadcaster_id = get_broadcaster_id(
            self.token, self.client_id, self.channel_name
        )
        backoff = 1
        while self._running:
            try:
                await self._connect(broadcaster_id)
                backoff = 1
            except Exception as e:
                logger.error("Twitch connection error: %s", e)
                self.on_status_change("reconnecting")
                backoff = min(backoff * 2, 60)
                await asyncio.sleep(backoff)

    async def _connect(self, broadcaster_id: str) -> None:
        async with websockets.connect(EVENTSUB_WS) as ws:
            self.on_status_change("connected")
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("metadata", {}).get("message_type")

                if msg_type == "session_welcome":
                    session_id = msg["payload"]["session"]["id"]
                    await asyncio.to_thread(
                        subscribe_to_redemptions,
                        self.token, self.client_id, broadcaster_id, session_id
                    )

                elif msg_type == "notification":
                    event = msg.get("payload", {}).get("event", {})
                    reward_title = event.get("reward", {}).get("title", "")
                    if reward_title == self.reward_name:
                        username = event.get("user_login", "")
                        text = event.get("user_input", "")
                        if username and text:
                            self.on_redemption(username, text)

    def stop(self) -> None:
        self._running = False
