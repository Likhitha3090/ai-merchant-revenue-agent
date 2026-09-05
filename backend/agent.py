import os
import json
from pathlib import Path

from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

from backend.audit import log_event


# =========================================================
# ENVIRONMENT / GROQ
# =========================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY was not found in .env")

client = Groq(api_key=GROQ_API_KEY)


# =========================================================
# PRODUCT CATALOG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCT_FILE = BASE_DIR / "data" / "products.json"


def load_products():
    """
    Load all products from the catalog.
    """

    with open(PRODUCT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# =========================================================
# PRODUCT SEARCH
# =========================================================

def search_products(query: str):
    """
    Search the product catalog using the customer's query.

    If the query is empty, return the complete catalog.
    """

    products = load_products()

    # Important:
    # An empty query means "return all products".
    if not query.strip():
        return products

    query_words = query.lower().split()

    matches = []

    for product in products:

        searchable_text = (
            product["name"]
            + " "
            + product["category"]
            + " "
            + product["description"]
            + " "
            + " ".join(product["tags"])
        ).lower()

        score = sum(
            1
            for word in query_words
            if word in searchable_text
        )

        if score > 0:
            matches.append((score, product))

    # Highest relevance first
    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return [
        product
        for score, product in matches
    ]


# =========================================================
# CATEGORY + BUDGET + STOCK FILTERING
# =========================================================

def filter_products(
    products,
    category=None,
    budget=None
):
    """
    Apply deterministic business rules.

    Rules:
    - Category/intent matching
    - Budget enforcement
    - Stock availability
    """

    filtered = products

    # -----------------------------------------------------
    # CATEGORY / INTENT FILTER
    # -----------------------------------------------------

    if category:

        category_words = (
            category.lower().split()
        )

        filtered = [
            product
            for product in filtered

            if any(
                word in (
                    product["name"]
                    + " "
                    + product["category"]
                    + " "
                    + product["description"]
                    + " "
                    + " ".join(product["tags"])
                ).lower()

                for word in category_words
            )
        ]

    # -----------------------------------------------------
    # BUDGET FILTER
    # -----------------------------------------------------

    if budget is not None:

        filtered = [
            product
            for product in filtered

            if product["price"] <= budget
        ]

    # -----------------------------------------------------
    # STOCK FILTER
    # -----------------------------------------------------

    filtered = [
        product
        for product in filtered

        if product["stock"] > 0
    ]

    return filtered


# =========================================================
# PYDANTIC MODELS
# =========================================================

class Recommendation(BaseModel):
    recommended_product_id: str
    reason: str
    budget: int | None = None


class CustomerIntent(BaseModel):
    category: str | None = None
    budget: int | None = None


# =========================================================
# CUSTOMER INTENT PARSER
# =========================================================

def parse_customer_request(user_query: str):
    """
    Extract category and budget from a natural-language
    customer request.
    """

    response = client.chat.completions.create(

        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "system",

                "content": """
You extract shopping requirements from customer requests.

Return ONLY valid JSON with:
- category
- budget

Rules:
1. category should be a short product category or use null if unclear.
2. budget must be a JSON number or null.
3. Do not include currency symbols in budget.
4. Treat unspecified budgets as null.
5. Treat prices and budgets as Indian Rupees (INR).

Example:

Customer:
"I need something for coding under ₹1000"

Return:
{
    "category": "coding",
    "budget": 1000
}
"""
            },

            {
                "role": "user",
                "content": user_query
            }
        ],

        response_format={
            "type": "json_object"
        }
    )

    result = json.loads(
        response.choices[0].message.content
    )

    intent = CustomerIntent(**result)

    # -----------------------------------------------------
    # AUDIT LOG
    # -----------------------------------------------------

    log_event(
        "INTENT_PARSED",
        {
            "query": user_query,
            "category": intent.category,
            "budget": intent.budget
        }
    )

    return intent


# =========================================================
# AI MERCHANT AGENT
# =========================================================

def run_agent(user_query: str):
    """
    Run the complete AI merchant recommendation flow.

    Flow:

    Customer query
        ↓
    Intent extraction
        ↓
    Product search
        ↓
    Category/budget/stock filtering
        ↓
    AI recommendation
        ↓
    Safety validation
    """

    # -----------------------------------------------------
    # STEP 1: EXTRACT CUSTOMER INTENT
    # -----------------------------------------------------

    intent = parse_customer_request(
        user_query
    )

    # -----------------------------------------------------
    # STEP 2: SEARCH PRODUCT CATALOG
    # -----------------------------------------------------

    products = search_products(
        user_query
    )

    # -----------------------------------------------------
    # STEP 3: APPLY DETERMINISTIC RULES
    # -----------------------------------------------------

    products = filter_products(
        products,
        category=intent.category,
        budget=intent.budget
    )

    # -----------------------------------------------------
    # STEP 4: HANDLE NO MATCH
    # -----------------------------------------------------

    if not products:

        log_event(
            "NO_PRODUCT_MATCH",
            {
                "query": user_query,
                "category": intent.category,
                "budget": intent.budget
            }
        )

        return {
            "success": False,
            "message": "No products match your requirements."
        }

    # -----------------------------------------------------
    # STEP 5: SEND ONLY VALID PRODUCTS TO THE LLM
    # -----------------------------------------------------

    product_context = json.dumps(
        products,
        indent=2
    )

    response = client.chat.completions.create(

        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "system",

                "content": """
You are an AI Merchant Revenue Agent.

Your job is to recommend products from the provided catalog.

Rules:

1. Recommend ONLY products from the provided catalog.
2. Never invent product IDs, names, prices, or stock.
3. All prices are in Indian Rupees (INR).
4. Respect the customer's budget.
5. Choose the most suitable product.
6. Return ONLY valid JSON.
7. The JSON must contain:
   - recommended_product_id
   - reason
   - budget
8. The budget MUST be a JSON number, not a string.
9. Do NOT include ₹, $, commas, or any currency symbol in the budget value.
10. Example:
    If the customer says ₹1000,
    return "budget": 1000.
"""
            },

            {
                "role": "user",

                "content": f"""
Customer request:

{user_query}


Available products:

{product_context}


Return the best product recommendation as JSON.
"""
            }
        ],

        response_format={
            "type": "json_object"
        }
    )

    # -----------------------------------------------------
    # STEP 6: PARSE STRUCTURED AI RESPONSE
    # -----------------------------------------------------

    result = json.loads(
        response.choices[0].message.content
    )

    recommendation = Recommendation(
        **result
    )

    # -----------------------------------------------------
    # STEP 7: SAFETY CHECK
    # -----------------------------------------------------
    # Make sure the LLM selected a product that actually
    # exists in the already-filtered catalog.

    valid_ids = {
        product["id"]
        for product in products
    }

    if (
        recommendation.recommended_product_id
        not in valid_ids
    ):

        fallback_product = products[0]

        recommendation = Recommendation(

            recommended_product_id=
                fallback_product["id"],

            reason=(
                "Best match within your "
                "requirements: "
                f"{fallback_product['name']}."
            ),

            budget=intent.budget
        )

    # -----------------------------------------------------
    # STEP 8: AUDIT RECOMMENDATION
    # -----------------------------------------------------

    log_event(
        "PRODUCT_RECOMMENDED",
        {
            "query": user_query,
            "product_id":
                recommendation.recommended_product_id,
            "budget":
                recommendation.budget
        }
    )

    # -----------------------------------------------------
    # STEP 9: RETURN RESULT
    # -----------------------------------------------------

    return {
        "success": True,

        "recommendation":
            recommendation.model_dump()
    }


# =========================================================
# DIRECT TERMINAL TEST
# =========================================================

if __name__ == "__main__":

    query = input(
        "Customer: "
    )

    result = run_agent(
        query
    )

    print(
        "\nAI Merchant Agent:"
    )

    print(
        result
    )