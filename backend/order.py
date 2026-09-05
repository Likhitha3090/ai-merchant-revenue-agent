import uuid
from datetime import datetime

from backend.audit import log_event
from backend.cart import build_cart
from backend.database import SessionLocal
from backend.models import Order, OrderItem


# =========================================================
# CREATE ORDER
# =========================================================

def create_order(items):
    """
    Create an order and persist it in PostgreSQL.

    Product prices are rebuilt from the server-side catalog
    using build_cart(), so the client cannot manipulate prices.
    """

    # -----------------------------------------------------
    # 1. Validate cart using the product catalog
    # -----------------------------------------------------

    cart_result = build_cart(items)

    if not cart_result["success"]:
        return cart_result

    cart = cart_result["cart"]


    # -----------------------------------------------------
    # 2. Generate local order ID
    # -----------------------------------------------------

    order_id = (
        f"ORD-{uuid.uuid4().hex[:8].upper()}"
    )


    # -----------------------------------------------------
    # 3. Create database session
    # -----------------------------------------------------

    db = SessionLocal()


    try:

        # -------------------------------------------------
        # 4. Create order record
        # -------------------------------------------------

        db_order = Order(
            id=order_id,
            amount=cart["subtotal"],
            currency="INR",
            status="PENDING_PAYMENT",
            created_at=datetime.utcnow()
        )

        db.add(db_order)


        # -------------------------------------------------
        # 5. Create order items
        # -------------------------------------------------

        for item in cart["items"]:

            db_item = OrderItem(

                order_id=order_id,

                product_id=item["product_id"],

                product_name=item["name"],

                quantity=item["quantity"],

                unit_price=item["unit_price"],

                total_price=item["total"]
            )

            db.add(db_item)


        # -------------------------------------------------
        # 6. Save transaction
        # -------------------------------------------------

        db.commit()


        # -------------------------------------------------
        # 7. Return the same structure your frontend expects
        # -------------------------------------------------

        order = {
            "order_id": order_id,

            "currency": "INR",

            "amount": cart["subtotal"],

            "status": "PENDING_PAYMENT",

            "created_at":
                db_order.created_at.isoformat(),

            "items": cart["items"]
        }


        # -------------------------------------------------
        # 8. Audit event
        # -------------------------------------------------

        log_event(
            "ORDER_CREATED",
            {
                "order_id": order_id,

                "amount":
                    cart["subtotal"],

                "currency":
                    "INR",

                "status":
                    "PENDING_PAYMENT"
            }
        )


        return {
            "success": True,
            "order": order
        }


    except Exception as e:

        # -------------------------------------------------
        # Roll back transaction if anything fails.
        # -------------------------------------------------

        db.rollback()

        print(
            f"Order creation error: {e}"
        )

        return {
            "success": False,
            "message":
                "Failed to create order."
        }


    finally:

        db.close()


# =========================================================
# MARK ORDER AS PAID
# =========================================================

def mark_order_paid(order_id):
    """
    Mark an existing PostgreSQL order as PAID.
    """

    db = SessionLocal()


    try:

        # -------------------------------------------------
        # Find order
        # -------------------------------------------------

        db_order = (
            db.query(Order)
            .filter(
                Order.id == order_id
            )
            .first()
        )


        if not db_order:

            return {
                "success": False,
                "message": "Order not found."
            }


        # -------------------------------------------------
        # Prevent unnecessary repeated payment updates
        # -------------------------------------------------

        if db_order.status == "PAID":

            order = _build_order_response(
                db,
                db_order
            )

            return {
                "success": True,
                "order": order
            }


        # -------------------------------------------------
        # Update status
        # -------------------------------------------------

        db_order.status = "PAID"

        db.commit()

        db.refresh(db_order)


        # -------------------------------------------------
        # Build response
        # -------------------------------------------------

        order = _build_order_response(
            db,
            db_order
        )


        # -------------------------------------------------
        # Audit event
        # -------------------------------------------------

        log_event(
            "ORDER_PAID",
            {
                "order_id":
                    db_order.id,

                "amount":
                    db_order.amount,

                "currency":
                    db_order.currency
            }
        )


        return {
            "success": True,
            "order": order
        }


    except Exception as e:

        db.rollback()

        print(
            f"Mark order paid error: {e}"
        )

        return {
            "success": False,
            "message":
                "Failed to update order."
        }


    finally:

        db.close()


# =========================================================
# GET ORDER
# =========================================================

def get_order(order_id):
    """
    Retrieve an order from PostgreSQL.
    """

    db = SessionLocal()


    try:

        db_order = (
            db.query(Order)
            .filter(
                Order.id == order_id
            )
            .first()
        )


        if not db_order:

            return {
                "success": False,
                "message": "Order not found."
            }


        order = _build_order_response(
            db,
            db_order
        )


        return {
            "success": True,
            "order": order
        }


    except Exception as e:

        print(
            f"Get order error: {e}"
        )

        return {
            "success": False,
            "message":
                "Failed to retrieve order."
        }


    finally:

        db.close()


# =========================================================
# BUILD ORDER RESPONSE
# =========================================================

def _build_order_response(
    db,
    db_order
):
    """
    Convert SQLAlchemy order model into
    the dictionary structure used by the API.
    """

    items = []

    for item in db_order.items:

        items.append(
            {
                "product_id":
                    item.product_id,

                "name":
                    item.product_name,

                "quantity":
                    item.quantity,

                "unit_price":
                    item.unit_price,

                "total":
                    item.total_price
            }
        )


    return {
        "order_id":
            db_order.id,

        "currency":
            db_order.currency,

        "amount":
            db_order.amount,

        "status":
            db_order.status,

        "created_at":
            db_order.created_at.isoformat(),

        "items":
            items
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    test_items = [
        {
            "product_id": "P001",
            "quantity": 1
        },
        {
            "product_id": "P002",
            "quantity": 1
        }
    ]


    result = create_order(
        test_items
    )


    print(result)