from sqlalchemy import text

from backend.database import engine


def test_database_connection():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text("SELECT version();")
            )

            version = result.scalar()

            print("✅ PostgreSQL connection successful!")
            print(f"PostgreSQL version: {version}")

    except Exception as e:

        print("❌ PostgreSQL connection failed.")
        print(f"Error: {e}")


if __name__ == "__main__":
    test_database_connection()