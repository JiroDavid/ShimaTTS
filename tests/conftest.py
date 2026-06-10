import pytest
from src.config import Config


@pytest.fixture
def basic_config():
    return Config(
        twitch_token="test_token",
        twitch_client_id="test_client_id",
        channel_name="testchannel",
        reward_name="TTS",
        voice_sample="/test/voice.wav",
        overlay_gif="/test/shima.gif",
    )
