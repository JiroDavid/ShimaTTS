from better_profanity import profanity

_WHITELIST = [
    "sex", "sexy", "sexual", "penis", "vagina", "boob", "boobs",
    "butt", "ass", "arse", "fuck", "fucking", "fucked", "shit",
    "damn", "bitch", "crap", "hell", "piss", "cock", "dick",
    "pussy", "bastard", "whore", "slut", "horny",
]

profanity.load_censor_words(whitelist_words=_WHITELIST)


def is_allowed(message: str, max_length: int) -> bool:
    if len(message) > max_length:
        return False
    if profanity.contains_profanity(message):
        return False
    return True
