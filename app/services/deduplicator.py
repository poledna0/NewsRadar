import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("URL precisa usar HTTP ou HTTPS, possuir host e não conter credenciais")
    host = parts.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    host_label = f"[{host}]" if ":" in host else host
    port = parts.port
    netloc = host_label if port is None or (scheme, port) in {("http", 80), ("https", 443)} else f"{host_label}:{port}"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query_items)), ""))


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def title_similarity(first: str, second: str) -> float:
    left, right = normalize_title(first), normalize_title(second)
    if not left or not right:
        return 0.0
    sequence_score = SequenceMatcher(None, left, right).ratio()
    left_words, right_words = set(left.split()), set(right.split())
    overlap_score = len(left_words & right_words) / max(1, len(left_words | right_words))
    return max(sequence_score, overlap_score)


def event_key(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()[:24]


def find_title_duplicate(title: str, candidates, threshold: float = 0.88):
    return next((article for article in candidates if title_similarity(title, article.title) >= threshold), None)