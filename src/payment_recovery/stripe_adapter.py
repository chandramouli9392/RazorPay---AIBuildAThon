from __future__ import annotations

from .models import FailureCategory, NormalizedFailure, StripeFailure

SECURITY_CODES = {"fraudulent", "lost_card", "stolen_card", "card_velocity_exceeded"}
INVALID_METHOD_CODES = {
    "expired_card",
    "incorrect_number",
    "invalid_number",
    "invalid_expiry_month",
    "invalid_expiry_year",
    "incorrect_cvc",
}
AUTHENTICATION_CODES = {"authentication_required", "payment_intent_authentication_failure"}
TEMPORARY_CODES = {"processing_error", "issuer_not_available", "reenter_transaction"}
HARD_DECLINE_CODES = {
    "do_not_honor",
    "generic_decline",
    "no_action_taken",
    "not_permitted",
    "restricted_card",
    "revocation_of_all_authorizations",
    "revocation_of_authorization",
    "stop_payment_order",
    "transaction_not_allowed",
}


def normalize_stripe_failure(failure: StripeFailure) -> NormalizedFailure:
    """Map Stripe-specific details into stable policy categories.

    `decline_code` is more specific than the top-level error `code`, which is
    commonly just `card_declined`. Advice is retained so policy can fail safe.
    """

    code = (failure.decline_code or failure.error_code or "unknown").lower()
    advice = (failure.advice_code or failure.network_advice_code or "").lower() or None

    if code in SECURITY_CODES:
        category = FailureCategory.SECURITY_OR_FRAUD
        reason = "Provider signalled a security-sensitive decline"
    elif advice == "do_not_try_again":
        category = FailureCategory.HARD_DECLINE
        reason = "Provider advice prohibits retrying this transaction"
    elif code in INVALID_METHOD_CODES:
        category = FailureCategory.INVALID_PAYMENT_METHOD
        reason = "Payment method details must be replaced or corrected"
    elif code in AUTHENTICATION_CODES:
        category = FailureCategory.AUTHENTICATION_REQUIRED
        reason = "Customer authentication is required"
    elif advice == "confirm_card_data":
        category = FailureCategory.INVALID_PAYMENT_METHOD
        reason = "Customer must confirm or correct payment method details"
    elif code == "insufficient_funds":
        category = FailureCategory.INSUFFICIENT_FUNDS
        reason = "Issuer reported insufficient funds"
    elif code in TEMPORARY_CODES or advice == "try_again_later":
        category = FailureCategory.TEMPORARY_PROCESSING
        reason = "Provider indicates a potentially temporary failure"
    elif code in HARD_DECLINE_CODES:
        category = FailureCategory.HARD_DECLINE
        reason = "Unattended retries are not permitted by the conservative policy"
    else:
        category = FailureCategory.UNKNOWN
        reason = "Unrecognized provider failure requires review"

    return NormalizedFailure(category, code, advice, reason)


def failure_from_payment_intent(payment_intent: dict[str, object]) -> StripeFailure:
    error = payment_intent.get("last_payment_error") or {}
    if not isinstance(error, dict):
        error = {}
    payment_method = error.get("payment_method") or {}
    if not isinstance(payment_method, dict):
        payment_method = {}
    card = payment_method.get("card") or {}
    if not isinstance(card, dict):
        card = {}
    network_advice = card.get("network_advice_code")
    return StripeFailure(
        error_code=_string(error.get("code")),
        decline_code=_string(error.get("decline_code")),
        advice_code=_string(error.get("advice_code")),
        network_advice_code=_string(network_advice),
    )


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None
