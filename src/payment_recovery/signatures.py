from __future__ import annotations

import hashlib
import hmac
import time


class SignatureVerificationError(ValueError):
    pass


def verify_stripe_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    *,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> None:
    """Verify a Stripe webhook signature against the unmodified request bytes."""

    if not raw_body or not secret or not signature_header:
        raise SignatureVerificationError("body, signature header, and secret are required")
    values: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        key, separator, value = item.strip().partition("=")
        if separator and key and value:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
        signatures = values["v1"]
    except (KeyError, ValueError, IndexError) as exc:
        raise SignatureVerificationError("malformed Stripe-Signature header") from exc

    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        raise SignatureVerificationError("signature timestamp outside tolerance")
    signed = str(timestamp).encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise SignatureVerificationError("signature mismatch")
