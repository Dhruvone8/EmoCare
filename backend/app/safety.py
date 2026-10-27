"""Deterministic text safety signals shared by inference and therapy pipelines."""
import re

CRISIS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsuicid\w*\b",
        r"\bkill(?:ing)?\s+myself\b",
        r"\bend(?:ing)?\s+my\s+life\b",
        r"\bwant(?:ing)?\s+to\s+die\b",
        r"\bbetter\s+off\s+dead\b",
        r"\bharm(?:ing)?\s+myself\b",
        r"\bhurt(?:ing)?\s+myself\b",
        r"\b(?:don'?t|do\s+not)\s+want\s+to\s+be\s+alive\b",
    )
]

ACUTE_DISTRESS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhopeless\b",
        r"\bno\s+hope\b",
        r"\bno\s+point\s+in\s+going\s+on\b",
        r"\b(?:don'?t|do\s+not)\s+see\s+(?:any\s+)?point\s+in\s+going\s+on\b",
        r"\bno\s+reason\s+to\s+(?:live|stay)\b",
        r"\bbetter\s+(?:off\s+)?without\s+me\b",
        r"\bno\s+way\s+out\b",
        r"\b(?:life|every\s+day|each\s+day)\s+(?:feels\s+|is\s+)?unbearable\b",
        r"\bworthless\b",
        r"\bfeel\s+like\s+a\s+burden\b",
        r"\bnothing\s+matters\s+anymore\b",
        r"\bno\s+future\b",
        r"\bdisappear\s+forever\b",
        r"\bgiven\s+up\s+on\s+life\b",
        r"\bconstant\s+despair\b",
        r"\blife\s+is\s+over\b",
        r"\bnothing\s+left\s+for\s+me\b",
        r"\bcan(?:not|'?t)\s+(?:keep\s+going|function\s+anymore)\b",
        r"\bbeyond\s+help\b",
        r"\b(?:no|losing\s+the)\s+will\s+to\s+live\b",
        r"\bnothing\s+to\s+look\s+forward\s+to\b",
        r"\bwant\s+(?:it\s+all|everything)\s+to\s+end\b",
    )
]

NEGATION_PREFIX = re.compile(
    r"\b(?:no\s+longer|not|never|don'?t|do\s+not|didn'?t|cannot|can\s+not)\b"
    r"[^.?!;]{0,35}$",
    re.IGNORECASE,
)


def _contains_unnegated_pattern(patterns: list[re.Pattern], text: str) -> bool:
    normalized_text = text.replace("’", "'")
    for pattern in patterns:
        for match in pattern.finditer(normalized_text):
            prefix = normalized_text[max(0, match.start() - 45):match.start()]
            if not NEGATION_PREFIX.search(prefix):
                return True
    return False


def is_crisis_signal(text: str) -> bool:
    """Detect explicit suicidal ideation or self-harm requiring crisis handling."""
    return _contains_unnegated_pattern(CRISIS_PATTERNS, text)


def has_acute_distress_signal(text: str) -> bool:
    """Detect acute hopelessness or self-harm language that must remain High risk."""
    return is_crisis_signal(text) or _contains_unnegated_pattern(
        ACUTE_DISTRESS_PATTERNS,
        text,
    )
