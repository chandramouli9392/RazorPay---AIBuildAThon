import pytest

from payment_recovery.models import FailureCategory, StripeFailure
from payment_recovery.stripe_adapter import normalize_stripe_failure


@pytest.mark.parametrize(
    ("failure", "category"),
    [
        (StripeFailure("card_declined", "insufficient_funds"), FailureCategory.INSUFFICIENT_FUNDS),
        (StripeFailure("expired_card"), FailureCategory.INVALID_PAYMENT_METHOD),
        (StripeFailure("card_declined", "fraudulent"), FailureCategory.SECURITY_OR_FRAUD),
        (StripeFailure("card_declined", "lost_card"), FailureCategory.SECURITY_OR_FRAUD),
        (StripeFailure("card_declined", "stolen_card"), FailureCategory.SECURITY_OR_FRAUD),
        (StripeFailure("authentication_required"), FailureCategory.AUTHENTICATION_REQUIRED),
        (StripeFailure("processing_error"), FailureCategory.TEMPORARY_PROCESSING),
        (StripeFailure("card_declined", "do_not_honor"), FailureCategory.HARD_DECLINE),
        (StripeFailure("card_declined", "generic_decline"), FailureCategory.HARD_DECLINE),
        (StripeFailure("new_provider_code"), FailureCategory.UNKNOWN),
    ],
)
def test_normalizes_provider_failures(failure, category):
    assert normalize_stripe_failure(failure).category == category


def test_decline_code_takes_precedence_over_generic_error_code():
    result = normalize_stripe_failure(StripeFailure("card_declined", "insufficient_funds"))
    assert result.provider_code == "insufficient_funds"


def test_advice_code_can_force_conservative_hard_decline():
    result = normalize_stripe_failure(
        StripeFailure("card_declined", advice_code="do_not_try_again")
    )
    assert result.category == FailureCategory.HARD_DECLINE


def test_do_not_try_again_overrides_otherwise_retryable_insufficient_funds():
    result = normalize_stripe_failure(
        StripeFailure("card_declined", "insufficient_funds", advice_code="do_not_try_again")
    )
    assert result.category == FailureCategory.HARD_DECLINE


def test_try_again_later_is_temporary_for_unknown_code():
    result = normalize_stripe_failure(StripeFailure("card_declined", advice_code="try_again_later"))
    assert result.category == FailureCategory.TEMPORARY_PROCESSING
