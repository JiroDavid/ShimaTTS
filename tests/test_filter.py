import pytest
from src.filter import is_allowed


def test_allows_clean_message():
    assert is_allowed("hello chat, how are you", 200) is True


def test_rejects_message_over_limit():
    assert is_allowed("a" * 201, 200) is False


def test_allows_message_at_exact_limit():
    assert is_allowed("a" * 200, 200) is True


def test_allows_adult_language():
    assert is_allowed("holy shit that was insane", 200) is True


def test_allows_anatomical_terms():
    assert is_allowed("penis and vagina are medical terms", 200) is True


def test_rejects_racial_slur():
    assert is_allowed("you fucking nigger", 200) is False


def test_rejects_hate_speech_phrase():
    assert is_allowed("kill all jews", 200) is False


def test_rejects_homophobic_slur():
    assert is_allowed("stop being such a faggot", 200) is False


def test_allows_empty_message():
    assert is_allowed("", 200) is True


def test_custom_length_limit():
    assert is_allowed("hi", 5) is True
    assert is_allowed("hello world", 5) is False
