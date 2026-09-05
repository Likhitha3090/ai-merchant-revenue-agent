from sqlalchemy import func

from backend.database import SessionLocal
from backend.models import Order, Payment, AuditLog


def get_dashboard_data():

    db = SessionLocal()

    try:

        # =================================================
        # ORDER STATISTICS
        # =================================================

        total_orders = (
            db.query(func.count(Order.id))
            .scalar()
            or 0
        )

        paid_orders = (
            db.query(func.count(Order.id))
            .filter(
                Order.status == "PAID"
            )
            .scalar()
            or 0
        )

        total_revenue = (
            db.query(func.sum(Order.amount))
            .filter(
                Order.status == "PAID"
            )
            .scalar()
            or 0
        )


        # =================================================
        # PAYMENT STATISTICS
        # =================================================

        verified_payments = (
            db.query(func.count(Payment.id))
            .filter(
                Payment.status == "VERIFIED"
            )
            .scalar()
            or 0
        )


        # =================================================
        # RECENT ORDERS
        # =================================================

        recent_orders = (
            db.query(Order)
            .order_by(
                Order.created_at.desc()
            )
            .limit(10)
            .all()
        )


        orders = []

        for order in recent_orders:

            orders.append(
                {
                    "order_id": order.id,
                    "amount": order.amount,
                    "currency": order.currency,
                    "status": order.status,
                    "created_at":
                        order.created_at.isoformat()
                }
            )


        # =================================================
        # RECENT AUDIT ACTIVITY
        # =================================================

        recent_events = (
            db.query(AuditLog)
            .order_by(
                AuditLog.timestamp.desc()
            )
            .limit(15)
            .all()
        )


        events = []

        for event in recent_events:

            events.append(
                {
                    "timestamp":
                        event.timestamp.isoformat(),

                    "event_type":
                        event.event_type,

                    "order_id":
                        event.order_id,

                    "details":
                        event.details or {}
                }
            )


        # =================================================
        # RETURN DASHBOARD DATA
        # =================================================

        return {
            "success": True,

            "summary": {
                "total_orders":
                    total_orders,

                "paid_orders":
                    paid_orders,

                "total_revenue":
                    total_revenue,

                "verified_payments":
                    verified_payments
            },

            "recent_orders":
                orders,

            "recent_events":
                events
        }


    except Exception as exc:

        print(
            f"Dashboard error: {exc}"
        )

        return {
            "success": False,
            "message":
                "Unable to load dashboard data."
        }


    finally:

        db.close()