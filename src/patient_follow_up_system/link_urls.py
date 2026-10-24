"""Stable patient links and a configurable, externally reachable QR origin."""

import hashlib
import hmac
import os
import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from patient_follow_up_system.auth import require_env


def patient_link_token(nonce: str) -> str:
    return hmac.new(
        require_env("AUTH_SECRET_KEY").encode(),
        ("patient-intake:" + nonce).encode(),
        hashlib.sha256,
    ).hexdigest()


def public_base_url(request: Request) -> str:
    value = (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)*/?", parsed.path)
    ):
        raise HTTPException(503, "PUBLIC_BASE_URL 必须是可访问的 http(s) 站点地址。")
    return value
