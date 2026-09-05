from datetime import datetime

from backend.database import SessionLocal
from backend.models import AuditLog


# =========================================================
# RECORD AUDIT EVENT
# =========================================================

def log_event(event_type, details=None):
    """
    Store an important system event in PostgreSQL.

    The function returns the same dictionary structure
    previously used by the application.
    """

    db = SessionLocal()

    try:

        event_details = details or {}

        # Create database record
        audit_record = AuditLog(
            event_type=event_type,
            order_id=event_details.get("order_id"),
            details=event_details,
            timestamp=datetime.utcnow()
        )

        db.add(audit_record)

        db.commit()

        db.refresh(audit_record)

        # Return application-friendly structure
        return {
            "timestamp":
                audit_record.timestamp.isoformat(),

            "event_type":
                audit_record.event_type,

            "details":
                audit_record.details or {}
        }

    except Exception as exc:

        db.rollback()

        # Audit logging should not break the
        # main transaction if logging fails.
        print(
            f"⚠️ Audit logging failed: {exc}"
        )

        return {
            "timestamp":
                datetime.utcnow().isoformat(),

            "event_type":
                event_type,

            "details":
                details or {}
        }

    finally:

        db.close()


# =========================================================
# GET AUDIT LOG
# =========================================================

def get_audit_log():
    """
    Retrieve audit events from PostgreSQL.
    """

    db = SessionLocal()

    try:

        records = (
            db.query(AuditLog)
            .order_by(
                AuditLog.timestamp.asc()
            )
            .all()
        )

        events = []

        for record in records:

            events.append(
                {
                    "timestamp":
                        record.timestamp.isoformat(),

                    "event_type":
                        record.event_type,

                    "details":
                        record.details or {}
                }
            )

        return events

    except Exception as exc:

        print(
            f"⚠️ Failed to retrieve audit log: {exc}"
        )

        return []

    finally:

        db.close()