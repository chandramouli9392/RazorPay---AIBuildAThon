import hashlib
import hmac

import pytest

from payment_recovery.signatures import SignatureVerificationError, verify_stripe_signature

SECRET = "whsec_test_secret"
NOW = 1_786_277_600
BODY = b'{"id":"evt_1","type":"payment_intent.payment_failed"}'


def signature(body=BODY, timestamp=NOW, secret=SECRET):
    payload = str(timestamp).encode() + b"." + body
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_valid_signature_uses_exact_raw_bytes():
    verify_stripe_signature(BODY, signature(), SECRET, now=NOW)
    with pytest.raises(SignatureVerificationError, match="mismatch"):
        verify_stripe_signature(BODY + b"\n", signature(), SECRET, now=NOW)


def test_accepts_any_valid_v1_during_secret_rotation():
    header = f"t={NOW},v1=invalid,{signature().split(',', 1)[1]}"
    verify_stripe_signature(BODY, header, SECRET, now=NOW)


@pytest.mark.parametrize("timestamp", [NOW - 301, NOW + 301])
def test_rejects_old_and_future_timestamps(timestamp):
    with pytest.raises(SignatureVerificationError, match="outside tolerance"):
        verify_stripe_signature(BODY, signature(timestamp=timestamp), SECRET, now=NOW)


@pytest.mark.parametrize("header", ["", "v1=abc", "t=nope,v1=abc", "t=1"])
def test_rejects_missing_or_malformed_headers(header):
    with pytest.raises(SignatureVerificationError):
        verify_stripe_signature(BODY, header, SECRET, now=NOW)
