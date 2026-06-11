import re
from typing import Iterable

from better_profanity import profanity

_WHITELIST = [
    "sex", "sexy", "sexual", "penis", "vagina", "boob", "boobs",
    "butt", "ass", "arse", "fuck", "fucking", "fucked", "shit",
    "damn", "bitch", "crap", "hell", "piss", "cock", "dick",
    "pussy", "bastard", "whore", "slut", "horny",
]

profanity.load_censor_words(whitelist_words=_WHITELIST)


def is_allowed(message: str, max_words: int, blocked_words: Iterable[str] = ()) -> bool:
    if len(message.split()) > max_words:
        return False
    if profanity.contains_profanity(message):
        return False
    lowered = message.lower()
    for word in blocked_words:
        if word and re.search(rf"\b{re.escape(word)}\b", lowered):
            return False
    return True
