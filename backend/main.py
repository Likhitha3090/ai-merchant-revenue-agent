from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.agent import run_agent, search_products, load_products
from backend.audit import get_audit_log
from backend.order import create_order
from backend.payment import (
    create_payment_for_order,
    verify_payment,
    simulate_payment_failure
)
from backend.upsell import get_upsell
from backend.dashboard import get_dashboard_data


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="AI Merchant Revenue Agent",
    description="AI-powered product discovery, upselling and secure checkout system.",
    version="1.0.0"
)


# =========================================================
# REQUEST MODELS
# =========================================================

class SearchRequest(BaseModel):
    query: str


class UpsellRequest(BaseModel):
    product_id: str


class OrderRequest(BaseModel):
    cart: dict


class PaymentItem(BaseModel):
    product_id: str
    quantity: int


class PaymentRequest(BaseModel):
    items: list[PaymentItem]


class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# =========================================================
# HEALTH / HOME
# =========================================================

@app.get("/")
def home():
    return {
        "message": "AI Merchant Revenue Agent API is running",
        "status": "healthy"
    }


# =========================================================
# PRODUCT CATALOG
# =========================================================

@app.get("/products")
def get_products():
    """
    Return the complete product catalog.
    """

    products = load_products()

    return {
        "count": len(products),
        "products": products
    }


# =========================================================
# PRODUCT SEARCH
# =========================================================

@app.post("/search")
def search(request: SearchRequest):
    """
    Search products using keyword matching.
    """

    products = search_products(request.query)

    return {
        "query": request.query,
        "count": len(products),
        "results": products
    }


# =========================================================
# AI RECOMMENDATION
# =========================================================

@app.post("/recommend")
def recommend(request: SearchRequest):
    """
    Run the AI merchant recommendation agent.
    """

    result = run_agent(request.query)

    return {
        "query": request.query,
        "recommendation": result
    }


# =========================================================
# UPSELL / CROSS-SELL
# =========================================================

@app.post("/upsell")
def upsell(request: UpsellRequest):
    """
    Return related products for the selected product.
    """

    return get_upsell(request.product_id)


# =========================================================
# LOCAL ORDER
# =========================================================

@app.post("/order")
def order(request: OrderRequest):
    """
    Create a validated local order.
    """

    return create_order(request.cart)


# =========================================================
# PAYMENT ORDER CREATION
# =========================================================

@app.post("/payment/create")
def create_payment(request: PaymentRequest):
    """
    Create a validated local order and the
    corresponding Razorpay Test Mode order.
    """

    items = [
        {
            "product_id": item.product_id,
            "quantity": item.quantity
        }
        for item in request.items
    ]

    return create_payment_for_order(items)


# =========================================================
# PAYMENT VERIFICATION
# =========================================================

@app.post("/payment/verify")
def payment_verify(request: PaymentVerificationRequest):
    """
    Verify Razorpay payment signature and
    update the corresponding local order.
    """

    return verify_payment(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    )


# =========================================================
# AUDIT LOG
# =========================================================

@app.get("/audit")
def audit():
    """
    Return the in-memory audit trail.
    """

    events = get_audit_log()

    return {
        "count": len(events),
        "events": events
    }


# =========================================================
# FRONTEND
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@app.get("/app")
def serve_frontend():
    """
    Serve the merchant agent frontend.
    """

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )

@app.get("/dashboard-data")
def dashboard_data():
    return get_dashboard_data()

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse(FRONTEND_DIR / "dashboard.html")

@app.post("/payment/test-failure/{order_id}")
def test_payment_failure(order_id: str):
    return simulate_payment_failure(order_id)