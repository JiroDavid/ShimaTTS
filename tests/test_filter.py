import pytest
from src.filter import is_allowed


def test_allows_clean_message():
    assert is_allowed("hello chat, how are you", 20) is True


def test_rejects_message_over_word_limit():
    assert is_allowed("word " * 21, 20) is False


def test_allows_message_at_exact_word_limit():
    assert is_allowed("word " * 20, 20) is True


def test_allows_adult_language():
    assert is_allowed("holy shit that was insane", 20) is True


def test_allows_anatomical_terms():
    assert is_allowed("penis and vagina are medical terms", 20) is True


def test_rejects_racial_slur():
    assert is_allowed("you fucking nigger", 20) is False


def test_rejects_hate_speech_phrase():
    assert is_allowed("kill all jews", 20) is False


def test_rejects_homophobic_slur():
    assert is_allowed("stop being such a faggot", 20) is False


def test_allows_empty_message():
    assert is_allowed("", 20) is True


def test_custom_word_limit():
    assert is_allowed("hi there", 5) is True
    assert is_allowed("one two three four five six", 5) is False


def test_rejects_custom_blocked_word():
    assert is_allowed("dont say bananas here", 20, ["bananas"]) is False


def test_blocked_word_is_case_insensitive():
    assert is_allowed("dont say BANANAS here", 20, ["bananas"]) is False


def test_blocked_word_matches_whole_words_only():
    assert is_allowed("the classic assassin", 20, ["ass"]) is True


def test_allows_when_blocked_word_absent():
    assert is_allowed("hello chat", 20, ["bananas"]) is True
