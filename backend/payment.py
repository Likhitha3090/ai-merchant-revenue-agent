import os
from datetime import datetime

import razorpay
from dotenv import load_dotenv

from backend.order import (
    create_order,
    get_order,
    mark_order_paid
)

from backend.audit import log_event

from backend.database import SessionLocal
from backend.models import Payment


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise ValueError(
        "Razorpay API credentials are missing from .env"
    )


# =========================================================
# RAZORPAY CLIENT
# =========================================================

client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET
    )
)


# =========================================================
# CREATE RAZORPAY ORDER
# =========================================================

def create_razorpay_order(
    amount_inr,
    local_order_id
):

    amount_paise = int(
        amount_inr * 100
    )

    receipt = (
        f"receipt_{local_order_id}"
    )

    data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt
    }

    razorpay_order = client.order.create(
        data=data
    )

    return {
        "success": True,
        "razorpay_order_id": razorpay_order["id"],
        "amount": razorpay_order["amount"],
        "currency": razorpay_order["currency"],
        "status": razorpay_order["status"],
        "receipt": razorpay_order["receipt"],
        "razorpay_key_id": RAZORPAY_KEY_ID
    }


# =========================================================
# CREATE PAYMENT
# =========================================================

def create_payment_for_order(items):

    # Create local order first.
    order_result = create_order(items)

    if not order_result["success"]:
        return order_result

    order = order_result["order"]

    # Create Razorpay order.
    try:

        razorpay_result = create_razorpay_order(
            order["amount"],
            order["order_id"]
        )

    except Exception as exc:

        log_event(
            "PAYMENT_CREATION_FAILED",
            {
                "order_id": order["order_id"],
                "error": str(exc)
            }
        )

        return {
            "success": False,
            "message": "Failed to create Razorpay order."
        }

    # -----------------------------------------------------
    # Save payment record in PostgreSQL
    # -----------------------------------------------------

    db = SessionLocal()

    try:

        payment_record = Payment(
            order_id=order["order_id"],
            razorpay_order_id=razorpay_result[
                "razorpay_order_id"
            ],
            razorpay_payment_id=None,
            status="CREATED",
            verified_at=None
        )

        db.add(payment_record)
        db.commit()

    except Exception as exc:

        db.rollback()

        log_event(
            "PAYMENT_DB_CREATION_FAILED",
            {
                "order_id": order["order_id"],
                "razorpay_order_id":
                    razorpay_result["razorpay_order_id"],
                "error": str(exc)
            }
        )

        return {
            "success": False,
            "message":
                "Payment created but could not be stored."
        }

    finally:

        db.close()

    # -----------------------------------------------------
    # Audit event
    # -----------------------------------------------------

    log_event(
        "PAYMENT_CREATED",
        {
            "order_id": order["order_id"],
            "razorpay_order_id":
                razorpay_result["razorpay_order_id"],
            "amount": razorpay_result["amount"],
            "currency": razorpay_result["currency"]
        }
    )

    return {
        "success": True,
        "order": order,
        "payment": razorpay_result
    }


# =========================================================
# VERIFY PAYMENT
# =========================================================

def verify_payment(
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature
):

    db = SessionLocal()

    try:

        # -------------------------------------------------
        # 1. Verify Razorpay signature
        # -------------------------------------------------

        client.utility.verify_payment_signature(
            {
                "razorpay_order_id":
                    razorpay_order_id,

                "razorpay_payment_id":
                    razorpay_payment_id,

                "razorpay_signature":
                    razorpay_signature
            }
        )

        log_event(
            "PAYMENT_SIGNATURE_VERIFIED",
            {
                "razorpay_order_id":
                    razorpay_order_id,

                "razorpay_payment_id":
                    razorpay_payment_id
            }
        )

        # -------------------------------------------------
        # 2. Fetch Razorpay order
        # -------------------------------------------------

        razorpay_order = client.order.fetch(
            razorpay_order_id
        )

        receipt = razorpay_order.get(
            "receipt",
            ""
        )

        if not receipt.startswith("receipt_"):

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Invalid Razorpay receipt",

                    "razorpay_order_id":
                        razorpay_order_id
                }
            )

            return {
                "success": False,
                "message":
                    "Invalid Razorpay receipt.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 3. Recover local order ID
        # -------------------------------------------------

        local_order_id = receipt.replace(
            "receipt_",
            "",
            1
        )

        # -------------------------------------------------
        # 4. Find local order
        # -------------------------------------------------

        local_order_result = get_order(
            local_order_id
        )

        if not local_order_result["success"]:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Local order not found",

                    "order_id":
                        local_order_id
                }
            )

            return {
                "success": False,
                "message":
                    "Local order not found.",
                "status":
                    "PAYMENT_VERIFIED_ORDER_NOT_FOUND"
            }

        local_order = local_order_result["order"]

        # -------------------------------------------------
        # 5. Find PostgreSQL payment record
        # -------------------------------------------------

        payment_record = (
            db.query(Payment)
            .filter(
                Payment.razorpay_order_id
                == razorpay_order_id
            )
            .first()
        )

        if not payment_record:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Payment record not found in database",

                    "razorpay_order_id":
                        razorpay_order_id,

                    "order_id":
                        local_order_id
                }
            )

            return {
                "success": False,
                "message":
                    "Payment record not found.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 6. Verify payment belongs to local order
        # -------------------------------------------------

        if payment_record.order_id != local_order_id:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Payment record belongs to another order",

                    "payment_order_id":
                        payment_record.order_id,

                    "local_order_id":
                        local_order_id
                }
            )

            return {
                "success": False,
                "message":
                    "Payment does not belong to this order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 7. Validate currency
        # -------------------------------------------------

        local_currency = local_order["currency"]

        razorpay_currency = razorpay_order.get(
            "currency"
        )

        if local_currency != razorpay_currency:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Currency mismatch",

                    "order_id":
                        local_order_id,

                    "local_currency":
                        local_currency,

                    "razorpay_currency":
                        razorpay_currency
                }
            )

            return {
                "success": False,
                "message":
                    "Payment currency does not match order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 8. Validate Razorpay order amount
        # -------------------------------------------------

        local_amount_paise = int(
            local_order["amount"] * 100
        )

        razorpay_amount_paise = int(
            razorpay_order.get(
                "amount",
                0
            )
        )

        if local_amount_paise != razorpay_amount_paise:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Order amount mismatch",

                    "order_id":
                        local_order_id,

                    "expected_amount_paise":
                        local_amount_paise,

                    "razorpay_amount_paise":
                        razorpay_amount_paise
                }
            )

            return {
                "success": False,
                "message":
                    "Payment amount does not match order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 9. Fetch actual Razorpay payment
        # -------------------------------------------------

        razorpay_payment = client.payment.fetch(
            razorpay_payment_id
        )

        # -------------------------------------------------
        # 10. Verify payment belongs to order
        # -------------------------------------------------

        payment_order_id = razorpay_payment.get(
            "order_id"
        )

        if payment_order_id != razorpay_order_id:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Payment does not belong to order",

                    "razorpay_order_id":
                        razorpay_order_id,

                    "payment_order_id":
                        payment_order_id,

                    "payment_id":
                        razorpay_payment_id
                }
            )

            return {
                "success": False,
                "message":
                    "Payment does not belong to this order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 11. Verify actual payment amount
        # -------------------------------------------------

        payment_amount_paise = int(
            razorpay_payment.get(
                "amount",
                0
            )
        )

        if payment_amount_paise != local_amount_paise:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Actual payment amount mismatch",

                    "order_id":
                        local_order_id,

                    "expected_amount_paise":
                        local_amount_paise,

                    "payment_amount_paise":
                        payment_amount_paise,

                    "payment_id":
                        razorpay_payment_id
                }
            )

            return {
                "success": False,
                "message":
                    "Actual payment amount does not match order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 12. Verify actual payment currency
        # -------------------------------------------------

        payment_currency = razorpay_payment.get(
            "currency"
        )

        if payment_currency != local_currency:

            log_event(
                "PAYMENT_SECURITY_FAILURE",
                {
                    "reason":
                        "Actual payment currency mismatch",

                    "order_id":
                        local_order_id,

                    "expected_currency":
                        local_currency,

                    "payment_currency":
                        payment_currency
                }
            )

            return {
                "success": False,
                "message":
                    "Actual payment currency does not match order.",
                "status":
                    "PAYMENT_FAILED"
            }

        # -------------------------------------------------
        # 13. Update PostgreSQL payment record
        # -------------------------------------------------

        payment_record.razorpay_payment_id = (
            razorpay_payment_id
        )

        payment_record.status = "VERIFIED"

        payment_record.verified_at = (
            datetime.utcnow()
        )

        db.commit()

        # -------------------------------------------------
        # 14. Audit
        # -------------------------------------------------

        log_event(
            "PAYMENT_VERIFIED",
            {
                "order_id":
                    local_order_id,

                "razorpay_order_id":
                    razorpay_order_id,

                "razorpay_payment_id":
                    razorpay_payment_id,

                "amount":
                    local_order["amount"],

                "currency":
                    local_currency
            }
        )

        # -------------------------------------------------
        # 15. Mark local order as PAID
        # -------------------------------------------------

        order_result = mark_order_paid(
            local_order_id
        )

        if not order_result["success"]:

            log_event(
                "ORDER_PAYMENT_UPDATE_FAILED",
                {
                    "order_id":
                        local_order_id,

                    "reason":
                        "Could not mark order as PAID"
                }
            )

            return {
                "success": False,
                "message":
                    "Payment verified but order could not be marked as paid.",
                "status":
                    "PAYMENT_VERIFIED_ORDER_UPDATE_FAILED"
            }

        # -------------------------------------------------
        # 16. Success
        # -------------------------------------------------

        return {
            "success": True,
            "message":
                "Payment verified successfully.",
            "status":
                "PAID",
            "order":
                order_result["order"],
            "razorpay_order_id":
                razorpay_order_id,
            "razorpay_payment_id":
                razorpay_payment_id
        }

    # =====================================================
    # INVALID SIGNATURE
    # =====================================================

    except razorpay.errors.SignatureVerificationError:

        db.rollback()

        log_event(
            "PAYMENT_SECURITY_FAILURE",
            {
                "reason":
                    "Signature verification failed",

                "razorpay_order_id":
                    razorpay_order_id,

                "razorpay_payment_id":
                    razorpay_payment_id
            }
        )

        return {
            "success": False,
            "message":
                "Payment signature verification failed.",
            "status":
                "PAYMENT_FAILED"
        }

    # =====================================================
    # OTHER ERRORS
    # =====================================================

    except Exception as exc:

        db.rollback()

        log_event(
            "PAYMENT_SECURITY_FAILURE",
            {
                "reason":
                    "Payment verification exception",

                "error":
                    str(exc),

                "razorpay_order_id":
                    razorpay_order_id,

                "razorpay_payment_id":
                    razorpay_payment_id
            }
        )

        return {
            "success": False,
            "message":
                "Payment verification error.",
            "status":
                "PAYMENT_FAILED"
        }

    finally:

        db.close()

# =========================================================
# SIMULATE PAYMENT FAILURE
# =========================================================

def simulate_payment_failure(order_id):
    """
    Simulate a payment failure for testing the
    recovery and audit workflow.

    This does NOT contact Razorpay.
    """

    db = SessionLocal()

    try:

        payment_record = (
            db.query(Payment)
            .filter(
                Payment.order_id == order_id
            )
            .first()
        )

        if not payment_record:

            return {
                "success": False,
                "message": "Payment record not found."
            }

        # Keep payment as failed.
        payment_record.status = "FAILED"

        db.commit()

        log_event(
            "PAYMENT_FAILED",
            {
                "order_id": order_id,
                "reason": "Simulated payment failure"
            }
        )

        return {
            "success": True,
            "status": "PAYMENT_FAILED",
            "message": (
                "Payment failed safely. "
                "The order remains pending and can be retried."
            ),
            "order_id": order_id
        }

    except Exception as exc:

        db.rollback()

        return {
            "success": False,
            "message": "Unable to simulate payment failure.",
            "error": str(exc)
        }

    finally:
       db.close()
