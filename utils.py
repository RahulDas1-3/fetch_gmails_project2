# utils.py

import base64
from typing import Any, Dict, List, Optional


def get_header(headers: List[Dict[str, Any]], name: str) -> Optional[str]:
    """Return a header value (case-insensitive) from Gmail headers list."""
    name_l = name.lower()
    for h in headers or []:
        if (h.get("name") or "").lower() == name_l:
            return h.get("value")
    return None


def _decode_body_data(data: str) -> str:
    """Decode Gmail's URL-safe base64 encoded data to text."""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_plain_text_from_payload(payload: Dict[str, Any]) -> str:
    """
    Walk Gmail message payload recursively and return first text/plain content found.
    """
    if not payload:
        return ""

    mime = payload.get("mimeType", "")

    # Direct text/plain
    if mime == "text/plain":
        body = payload.get("body", {}) or {}
        data = body.get("data")
        if data:
            return _decode_body_data(data)

    # Multipart: iterate parts
    for part in payload.get("parts", []) or []:
        txt = extract_plain_text_from_payload(part)
        if txt:
            return txt

    return ""