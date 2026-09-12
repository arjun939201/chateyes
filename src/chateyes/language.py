from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_SPACE_RE = re.compile(r"\s+")
_NONLETTER_RE = re.compile(r"[^a-zA-Z\u0900-\u097F\u0600-\u06FF\u0590-\u05FF\s]")

_SCRIPT_RANGES = (
    ("Arabic", ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF))),
    ("Hebrew", ((0x0590, 0x05FF),)),
    ("Devanagari", ((0x0900, 0x097F),)),
    ("Bengali", ((0x0980, 0x09FF),)),
    ("Gujarati", ((0x0A80, 0x0AFF),)),
    ("Gurmukhi", ((0x0A00, 0x0A7F),)),
    ("Tamil", ((0x0B80, 0x0BFF),)),
    ("Telugu", ((0x0C00, 0x0C7F),)),
    ("Kannada", ((0x0C80, 0x0CFF),)),
    ("Malayalam", ((0x0D00, 0x0D7F),)),
    ("Thai", ((0x0E00, 0x0E7F),)),
    ("Cyrillic", ((0x0400, 0x04FF),)),
    ("Greek", ((0x0370, 0x03FF),)),
)

# Phrase-level markers keep ordinary English words from being mislabeled.
_LATIN_HINTS = {
    "Hindi": {
        "kya", "hai", "hain", "nahi", "nahin", "nhi", "tum", "aap", "mujhe", "mko",
        "mera", "meri", "mere", "ko", "se", "marna", "maar", "khayega", "khaega",
        "behn", "bhai", "cousin", "ladka", "ladki", "kar", "karo", "mat", "kyu", "kyon",
    },
    "Urdu": {"kya", "hai", "hain", "nahi", "nahin", "nhi", "tum", "aap", "mujhe", "mko", "mera", "meri", "ko", "se"},
    "Arabic": {"ana", "anta", "anti", "huwa", "hiya", "habibi", "habibti", "wallah", "inshallah", "shukran"},
    "Hebrew": {"ani", "ata", "at", "ze", "zot", "lo", "ken", "toda", "shalom", "ma"},
}


def normalize_for_detection(text: str) -> str:
    """Normalize Unicode and common chat obfuscation without changing source text."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    # OCR frequently inserts punctuation between letters: m.a.a.r, m@r, etc.
    text = re.sub(r"(?<=[A-Za-z])\s*[._|~`^]+\s*(?=[A-Za-z])", "", text)
    return _SPACE_RE.sub(" ", text).strip()


def _script_counts(text: str) -> dict[str, int]:
    counts = {name: 0 for name, _ in _SCRIPT_RANGES}
    for char in text:
        codepoint = ord(char)
        for name, ranges in _SCRIPT_RANGES:
            if any(start <= codepoint <= end for start, end in ranges):
                counts[name] += 1
                break
    return counts


def detect_language(text: str) -> str:
    """Return a conservative language/script label for moderation metadata."""
    normalized = normalize_for_detection(text)
    counts = _script_counts(normalized)
    if normalized:
        script, count = max(counts.items(), key=lambda item: item[1])
        if count:
            if script == "Devanagari":
                return "Hindi"
            return script

    words = set(re.findall(r"[a-zA-Z]+", normalized.casefold()))
    scores = {language: len(words & hints) for language, hints in _LATIN_HINTS.items()}
    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score >= 2:
        return "Transliterated " + best_language
    return "English"
