import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCT_FILE = BASE_DIR / "data" / "products.json"


def load_products():
    with open(PRODUCT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def build_cart(items):
    """
    Build and validate a cart from product IDs and quantities.

    Example:
    [
        {"product_id": "P001", "quantity": 1},
        {"product_id": "P002", "quantity": 1}
    ]
    """

    products = load_products()

    product_map = {
        product["id"]: product
        for product in products
    }

    cart_items = []

    for item in items:
        product_id = item["product_id"]
        quantity = item["quantity"]

        if quantity <= 0:
            return {
                "success": False,
                "message": "Quantity must be greater than zero."
            }

        product = product_map.get(product_id)

        if not product:
            return {
                "success": False,
                "message": f"Product {product_id} not found."
            }

        if product["stock"] < quantity:
            return {
                "success": False,
                "message": f"Insufficient stock for {product['name']}."
            }

        # IMPORTANT:
        # Price always comes from our catalog.
        # Never trust a price supplied by the client or LLM.
        unit_price = product["price"]

        cart_items.append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": quantity,
            "unit_price": unit_price,
            "total": unit_price * quantity
        })

    subtotal = sum(
        item["total"]
        for item in cart_items
    )

    return {
        "success": True,
        "cart": {
            "items": cart_items,
            "subtotal": subtotal,
            "currency": "INR"
        }
    }


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

    result = build_cart(test_items)

    print(json.dumps(result, indent=2))