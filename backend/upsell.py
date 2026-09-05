import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCT_FILE = BASE_DIR / "data" / "products.json"


def load_products():
    with open(PRODUCT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_upsell(product_id: str):
    products = load_products()

    product_map = {
        product["id"]: product
        for product in products
    }

    if product_id not in product_map:
        return {
            "success": False,
            "message": "Product not found."
        }

    selected_product = product_map[product_id]

    related_ids = selected_product.get("related_products", [])

    recommendations = []

    for related_id in related_ids:
        related_product = product_map.get(related_id)

        if not related_product:
            continue

        # Never recommend out-of-stock products
        if related_product["stock"] <= 0:
            continue

        recommendations.append({
            "id": related_product["id"],
            "name": related_product["name"],
            "price": related_product["price"],
            "category": related_product["category"],
            "reason": f"Complements {selected_product['name']}"
        })

    return {
        "success": True,
        "base_product": {
            "id": selected_product["id"],
            "name": selected_product["name"],
            "price": selected_product["price"]
        },
        "upsell_options": recommendations
    }
if __name__ == "__main__":
    result = get_upsell("P001")
    print(json.dumps(result, indent=2))