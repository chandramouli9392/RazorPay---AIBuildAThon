from __future__ import annotations

import hashlib
import hmac


class RazorpaySignatureVerificationError(ValueError):
    """Exception raised when Razorpay webhook signature verification fails."""


def verify_razorpay_signature(
    raw_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify a Razorpay webhook signature against raw body bytes using HMAC-SHA256."""
    if not raw_body or not secret or not signature:
        raise RazorpaySignatureVerificationError(
            "raw_body, signature header, and secret are required"
        )

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature.strip()):
        raise RazorpaySignatureVerificationError("Razorpay signature mismatch")

    return True
