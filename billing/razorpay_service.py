import logging

import hashlib
import hmac

import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)


class RazorpayServiceError(Exception):
    """Raised when a Razorpay operation fails."""


def get_razorpay_client():
    """Create a Razorpay client using server-side credentials."""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise RazorpayServiceError(
            "Razorpay credentials are not configured."
        )

    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


def create_razorpay_order(amount_paise, receipt, notes=None):
    """
    Create a Razorpay order.

    amount_paise must be an integer in the smallest currency unit.
    For INR, ₹999 = 99900 paise.
    """
    if not isinstance(amount_paise, int) or isinstance(amount_paise, bool):
        raise ValueError("Amount must be an integer in paise.")

    if amount_paise <= 0:
        raise ValueError("Amount must be greater than zero.")

    try:
        client = get_razorpay_client()

        order = client.order.create(
            data={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": str(receipt),
                "notes": notes or {},
            }
        )

        return order

    except RazorpayServiceError:
        raise
    except Exception as exc:
        logger.exception("Failed to create Razorpay order.")
        raise RazorpayServiceError(
            "Unable to create payment order."
        ) from exc

def verify_payment_signature(
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
):
    """Verify the payment signature returned by Razorpay."""
    try:
        client = get_razorpay_client()

        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

        return True

    except razorpay.errors.SignatureVerificationError:
        logger.warning(
            "Razorpay payment signature verification failed."
        )
        return False

    except RazorpayServiceError:
        raise

    except Exception as exc:
        logger.exception("Razorpay signature verification error.")
        raise RazorpayServiceError(
            "Unable to verify payment signature."
        ) from exc

def fetch_razorpay_payment(razorpay_payment_id):
    """Fetch payment details directly from Razorpay."""
    try:
        client = get_razorpay_client()
        return client.payment.fetch(razorpay_payment_id)
    except RazorpayServiceError:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch Razorpay payment.")
        raise RazorpayServiceError(
            "Unable to fetch payment details."
        ) from exc

def verify_webhook_signature(payload, signature):
    """Verify a Razorpay webhook using its raw request body."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET

    if not secret or not signature:
        return False

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)