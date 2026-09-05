import json
from pathlib import Path

from backend.agent import run_agent, load_products


# =========================================================
# TEST CASES
# =========================================================

TEST_CASES = [
    {
        "query": "I need something for coding under 1000",
        "expected_max_price": 1000
    },
    {
        "query": "I need a laptop for programming",
        "expected_max_price": None
    },
    {
        "query": "I need a tablet for online classes under 20000",
        "expected_max_price": 20000
    },
    {
        "query": "I need a monitor for coding",
        "expected_max_price": None
    },
    {
        "query": "I need headphones for gaming",
        "expected_max_price": None
    },
    {
        "query": "I need something for online meetings",
        "expected_max_price": None
    },
    {
        "query": "I need a keyboard for programming",
        "expected_max_price": None
    },
    {
        "query": "I need a wireless mouse for office work",
        "expected_max_price": None
    },
    {
        "query": "I need a quantum computer under 500",
        "expected_max_price": 500
    },
    {
        "query": "I need a refrigerator under 10000",
        "expected_max_price": 10000
    }
]


# =========================================================
# LOAD CATALOG
# =========================================================

products = load_products()

product_map = {
    product["id"]: product
    for product in products
}


# =========================================================
# EVALUATION
# =========================================================

def evaluate():

    total = len(TEST_CASES)

    valid_recommendations = 0

    budget_compliant = 0

    in_stock = 0

    results = []


    for index, test_case in enumerate(
        TEST_CASES,
        start=1
    ):

        query = test_case["query"]

        expected_max_price = (
            test_case["expected_max_price"]
        )


        print()
        print("=" * 70)
        print(f"Test {index}/{total}")
        print(f"Query: {query}")
        print("=" * 70)


        try:

            result = run_agent(query)


            if not result.get("success"):

                results.append(
                    {
                        "query": query,
                        "success": False,
                        "reason":
                            result.get(
                                "message",
                                "No recommendation"
                            )
                    }
                )

                print("❌ No valid recommendation")

                continue


            recommendation = (
                result["recommendation"]
            )


            product_id = (
                recommendation[
                    "recommended_product_id"
                ]
            )


            product = product_map.get(
                product_id
            )


            # ---------------------------------------------
            # Product validation
            # ---------------------------------------------

            if not product:

                results.append(
                    {
                        "query": query,
                        "success": False,
                        "reason":
                            "Recommended product not in catalog"
                    }
                )

                print(
                    "❌ Recommended product not in catalog"
                )

                continue


            valid_recommendations += 1


            # ---------------------------------------------
            # Stock validation
            # ---------------------------------------------

            stock_ok = (
                product["stock"] > 0
            )

            if stock_ok:
                in_stock += 1


            # ---------------------------------------------
            # Budget validation
            # ---------------------------------------------

            budget_ok = True

            if expected_max_price is not None:

                budget_ok = (
                    product["price"]
                    <= expected_max_price
                )

                if budget_ok:
                    budget_compliant += 1

            else:

                # No explicit budget means
                # no budget constraint to evaluate.
                budget_compliant += 1


            result_record = {
                "query": query,

                "success": True,

                "product_id": product["id"],

                "product_name":
                    product["name"],

                "price":
                    product["price"],

                "stock":
                    product["stock"],

                "budget_ok":
                    budget_ok,

                "in_stock":
                    stock_ok
            }


            results.append(
                result_record
            )


            print(
                f"✅ {product['name']}"
            )

            print(
                f"   Price: ₹{product['price']}"
            )

            print(
                f"   Budget OK: {budget_ok}"
            )

            print(
                f"   In stock: {stock_ok}"
            )


        except Exception as exc:

            results.append(
                {
                    "query": query,
                    "success": False,
                    "reason": str(exc)
                }
            )

            print(
                f"❌ Error: {exc}"
            )


    # =====================================================
    # METRICS
    # =====================================================

    recommendation_rate = (
        valid_recommendations / total * 100
    )

    budget_rate = (
        budget_compliant / total * 100
    )

    stock_rate = (
        in_stock / total * 100
    )


    print()
    print()
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Total test cases:        {total}"
    )

    print(
        f"Valid recommendations:   "
        f"{valid_recommendations}/{total} "
        f"({recommendation_rate:.1f}%)"
    )

    print(
        f"Budget compliant:        "
        f"{budget_compliant}/{total} "
        f"({budget_rate:.1f}%)"
    )

    print(
        f"In-stock recommendations:"
        f" {in_stock}/{total} "
        f"({stock_rate:.1f}%)"
    )


    # =====================================================
    # SAVE RESULTS
    # =====================================================

    output_path = (
        Path(__file__).resolve().parent.parent
        / "evaluation_results.json"
    )


    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            {
                "summary": {
                    "total_tests":
                        total,

                    "valid_recommendations":
                        valid_recommendations,

                    "recommendation_rate":
                        round(
                            recommendation_rate,
                            2
                        ),

                    "budget_compliant":
                        budget_compliant,

                    "budget_compliance_rate":
                        round(
                            budget_rate,
                            2
                        ),

                    "in_stock":
                        in_stock,

                    "stock_rate":
                        round(
                            stock_rate,
                            2
                        )
                },

                "results":
                    results
            },

            file,

            indent=2
        )


    print()
    print(
        f"📄 Results saved to: "
        f"{output_path}"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    evaluate()