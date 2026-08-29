# Synthetic test data

All identifiers and addresses in repository fixtures are synthetic. `example.invalid` is used so test mail cannot be delivered accidentally.

The automated suite generates signed webhook bodies in memory. For Stripe-hosted test mode, use the PaymentMethods documented in [`docs/TESTING.md`](../../docs/TESTING.md).

Expected policy behavior:

- `expired_card`: invalid payment method, customer update required, no unattended retry;
- `insufficient_funds`: three-attempt bounded schedule;
- `fraudulent`, `lost_card`, `stolen_card`: security/manual review, no retry, no customer-facing fraud detail;
- `do_not_honor`: conservative hard decline, not automatically labelled fraud;
- `processing_error` or `try_again_later`: bounded temporary-processing schedule;
- unknown codes: fail safe to manual review.

Fixtures do not encode a probability of successful recovery and cannot support revenue or recovery-rate claims.
