import hashlib


def hash_description(text: str) -> str:
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
