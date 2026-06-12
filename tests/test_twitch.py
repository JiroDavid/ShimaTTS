import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.twitch import get_broadcaster_id, TwitchListener


def test_get_broadcaster_id_returns_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "12345678", "login": "testchannel"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.twitch.requests.get", return_value=mock_resp):
        uid = get_broadcaster_id("token", "client_id", "testchannel")
    assert uid == "12345678"


def test_get_broadcaster_id_raises_for_unknown_channel():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.twitch.requests.get", return_value=mock_resp):
        with pytest.raises(ValueError, match="not found"):
            get_broadcaster_id("token", "client_id", "unknown")


@pytest.mark.asyncio
async def test_listener_calls_on_redemption_for_matching_reward():
    redemptions = []

    listener = TwitchListener(
        token="tok",
        client_id="cid",
        channel_name="chan",
        reward_name="TTS",
        on_redemption=lambda u, m: redemptions.append((u, m)),
        on_status_change=lambda s: None,
    )

    welcome_msg = json.dumps({
        "metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "sess_abc"}},
    })
    redemption_msg = json.dumps({
        "metadata": {"message_type": "notification"},
        "payload": {
            "event": {
                "user_login": "viewer1",
                "user_input": "hello from chat",
                "reward": {"title": "TTS"},
            }
        },
    })

    messages = [welcome_msg, redemption_msg]

    async def _aiter(self):
        for m in messages:
            yield m

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = lambda self=mock_ws: _aiter(mock_ws)
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=False)

    with patch("src.twitch.get_broadcaster_id", return_value="999"), \
         patch("src.twitch.subscribe_to_redemptions"), \
         patch("src.twitch.websockets.connect", return_value=mock_ws):
        listener._running = True
        try:
            await asyncio.wait_for(listener._connect("999"), timeout=1.0)
        except (StopAsyncIteration, asyncio.TimeoutError):
            pass

    assert len(redemptions) == 1
    assert redemptions[0] == ("viewer1", "hello from chat")


@pytest.mark.asyncio
async def test_listener_ignores_wrong_reward_name():
    redemptions = []

    listener = TwitchListener(
        token="tok",
        client_id="cid",
        channel_name="chan",
        reward_name="TTS",
        on_redemption=lambda u, m: redemptions.append((u, m)),
        on_status_change=lambda s: None,
    )

    wrong_reward_msg = json.dumps({
        "metadata": {"message_type": "notification"},
        "payload": {
            "event": {
                "user_login": "viewer1",
                "user_input": "hi",
                "reward": {"title": "Hydrate"},
            }
        },
    })

    messages = [wrong_reward_msg]

    async def _aiter(self):
        for m in messages:
            yield m

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = lambda self=mock_ws: _aiter(mock_ws)
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=False)

    with patch("src.twitch.get_broadcaster_id", return_value="999"), \
         patch("src.twitch.subscribe_to_redemptions"), \
         patch("src.twitch.websockets.connect", return_value=mock_ws):
        try:
            await asyncio.wait_for(listener._connect("999"), timeout=1.0)
        except (StopAsyncIteration, asyncio.TimeoutError):
            pass

    assert len(redemptions) == 0


def _mock_ws(messages):
    async def _aiter(self):
        for m in messages:
            yield m

    ws = AsyncMock()
    ws.__aiter__ = lambda self=None: _aiter(ws)
    ws.__aenter__ = AsyncMock(return_value=ws)
    ws.__aexit__ = AsyncMock(return_value=False)
    return ws


@pytest.mark.asyncio
async def test_listener_follows_session_reconnect():
    redemptions = []

    listener = TwitchListener(
        token="tok",
        client_id="cid",
        channel_name="chan",
        reward_name="TTS",
        on_redemption=lambda u, m: redemptions.append((u, m)),
        on_status_change=lambda s: None,
    )

    first_ws = _mock_ws([
        json.dumps({
            "metadata": {"message_type": "session_welcome"},
            "payload": {"session": {"id": "sess_1"}},
        }),
        json.dumps({
            "metadata": {"message_type": "session_reconnect"},
            "payload": {"session": {"reconnect_url": "wss://reconnect.example/ws"}},
        }),
    ])
    second_ws = _mock_ws([
        json.dumps({
            "metadata": {"message_type": "session_welcome"},
            "payload": {"session": {"id": "sess_2"}},
        }),
        json.dumps({
            "metadata": {"message_type": "notification"},
            "payload": {
                "event": {
                    "user_login": "viewer1",
                    "user_input": "after reconnect",
                    "reward": {"title": "TTS"},
                }
            },
        }),
    ])

    with patch("src.twitch.subscribe_to_redemptions") as mock_sub, \
         patch("src.twitch.websockets.connect", side_effect=[first_ws, second_ws]) as mock_connect:
        await asyncio.wait_for(listener._connect("999"), timeout=1.0)

    assert mock_connect.call_args_list[1].args[0] == "wss://reconnect.example/ws"
    mock_sub.assert_called_once()
    assert redemptions == [("viewer1", "after reconnect")]
