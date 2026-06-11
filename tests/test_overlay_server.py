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
    assert data["max_message_words"] == 20
    assert data["blocked_words"] == []
    assert data["twitch_client_id"] == "test_client_id"


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
async def test_config_save_merge_preserves_unsent_fields(basic_config):
    from src.overlay.server import app
    basic_config.twitch_client_id = "custom_id"
    basic_config.port = 9999
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config") as mock_save:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/config/save", json={"channel_name": "newname"})
    assert resp.status_code == 200
    saved = mock_save.call_args.args[0]
    assert saved.channel_name == "newname"
    assert saved.twitch_client_id == "custom_id"
    assert saved.port == 9999


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


@pytest.mark.asyncio
async def test_logout_revokes_and_clears_token(basic_config):
    from src.overlay.server import app
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config") as mock_save, \
         patch("src.overlay.server.req.post") as mock_post:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "logged_out"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["data"]["token"] == "test_token"
    saved = mock_save.call_args.args[0]
    assert saved.twitch_token == ""
    assert saved.channel_name == "testchannel"


@pytest.mark.asyncio
async def test_logout_clears_token_when_revoke_fails(basic_config):
    from src.overlay.server import app
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config") as mock_save, \
         patch("src.overlay.server.req.post", side_effect=ConnectionError("offline")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    assert mock_save.call_args.args[0].twitch_token == ""


@pytest.mark.asyncio
async def test_logout_signals_app_server_restart(basic_config):
    from src.overlay.server import app, set_app_server
    fake_server = MagicMock(should_exit=False)
    set_app_server(fake_server)
    try:
        with patch("src.overlay.server.load_config", return_value=basic_config), \
             patch("src.overlay.server.save_config"), \
             patch("src.overlay.server.req.post"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/auth/logout")
    finally:
        set_app_server(None)
    assert resp.status_code == 200
    assert fake_server.should_exit is True


@pytest.fixture
def data_dir(tmp_path):
    with patch("src.overlay.server._data_dir", return_value=tmp_path):
        yield tmp_path


@pytest.mark.asyncio
async def test_list_files_returns_uploads(mock_config, data_dir):
    from src.overlay.server import app
    (data_dir / "voice.wav").write_bytes(b"RIFF")
    (data_dir / "alert.gif").write_bytes(b"GIF89a")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/files")
    assert resp.status_code == 200
    files = {f["name"]: f for f in resp.json()["files"]}
    assert files["voice.wav"]["kind"] == "audio"
    assert files["alert.gif"]["kind"] == "gif"


@pytest.mark.asyncio
async def test_get_file_serves_content(mock_config, data_dir):
    from src.overlay.server import app
    (data_dir / "voice.wav").write_bytes(b"RIFFdata")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/files/voice.wav")
    assert resp.status_code == 200
    assert resp.content == b"RIFFdata"


@pytest.mark.asyncio
async def test_get_file_rejects_traversal(mock_config, data_dir):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/files/..%2Fconfig.json")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_file_removes_and_clears_config(basic_config, data_dir):
    from src.overlay.server import app
    target = data_dir / "voice.wav"
    target.write_bytes(b"RIFF")
    basic_config.voice_sample = str(target)
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config") as mock_save:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/files/voice.wav")
    assert resp.status_code == 200
    assert not target.exists()
    assert resp.json()["config_cleared"] is True
    mock_save.assert_called_once()
    assert basic_config.voice_sample == ""


@pytest.mark.asyncio
async def test_upload_voice_keeps_filename(mock_config, data_dir):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/upload/voice", files={"file": ("my sample.wav", b"RIFF", "audio/wav")})
    assert resp.status_code == 200
    assert resp.json()["path"].endswith("my sample.wav")
    assert (data_dir / "my sample.wav").exists()


@pytest.mark.asyncio
async def test_upload_rejects_wrong_extension(mock_config, data_dir):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/upload/gif", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_config_data_includes_default_client_id(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config/data")
    assert "default_client_id" in resp.json()


@pytest.mark.asyncio
async def test_test_alert_broadcasts(mock_config):
    from src.overlay.server import app, _connections
    sent = []

    mock_ws = MagicMock()
    async def fake_send(payload):
        sent.append(json.loads(payload))
    mock_ws.send_text = fake_send
    _connections.add(mock_ws)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/test/alert", json={"username": "tester", "message": "hello"})
    finally:
        _connections.discard(mock_ws)

    assert resp.status_code == 200
    assert resp.json()["connections"] == 1
    assert sent[0]["username"] == "tester"
    assert sent[0]["message"] == "hello"
