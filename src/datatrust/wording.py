def pluralize(count: int, singular: str, plural: str = None) -> str:
    """Return a deterministic singular or plural noun for a numeric count."""
    return singular if count == 1 else (plural or f"{singular}s")


def count_phrase(count: int, singular: str, plural: str = None) -> str:
    """Return a count followed by its correctly inflected noun."""
    return f"{count} {pluralize(count, singular, plural)}"


def have_verb(count: int) -> str:
    return "has" if count == 1 else "have"


def be_verb(count: int, past: bool = False) -> str:
    if past:
        return "was" if count == 1 else "were"
    return "is" if count == 1 else "are"


def agree(count: int, singular: str, plural: str) -> str:
    """Choose a verb form that agrees with a numeric subject."""
    return singular if count == 1 else plural
