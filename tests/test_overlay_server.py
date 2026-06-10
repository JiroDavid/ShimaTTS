import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_config(basic_config):
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config"):
        yield basic_config


@pytest.mark.asyncio
async def test_overlay_route_returns_html(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/overlay")
    assert resp.status_code == 200
    assert "ShimaTTS" in resp.text


@pytest.mark.asyncio
async def test_config_page_returns_html(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config")
    assert resp.status_code == 200
    assert "<form" in resp.text


@pytest.mark.asyncio
async def test_config_data_returns_json(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config/data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel_name"] == "testchannel"
    assert data["port"] == 7878


@pytest.mark.asyncio
async def test_config_save_writes_config(mock_config, tmp_path):
    from src.overlay.server import app, save_config
    payload = {
        "twitch_token": "newtoken",
        "twitch_client_id": "newclient",
        "channel_name": "newchannel",
        "reward_name": "TTS",
        "voice_sample": "/voice.wav",
        "overlay_gif": "/gif.gif",
        "max_message_length": 150,
        "port": 7878,
    }
    with patch("src.overlay.server.save_config") as mock_save:
        from src.overlay.server import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/config/save", json=payload)
        assert resp.status_code == 200
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_sends_to_websocket():
    from src.overlay.server import broadcast, _connections
    mock_ws = MagicMock()

    sent = []
    async def fake_send(payload):
        sent.append(json.loads(payload))

    mock_ws.send_text = fake_send
    _connections.add(mock_ws)
    try:
        await broadcast("viewer1", "hello world", 2000)
    finally:
        _connections.discard(mock_ws)

    assert len(sent) == 1
    assert sent[0]["username"] == "viewer1"
    assert sent[0]["message"] == "hello world"
    assert sent[0]["duration_ms"] == 2000
