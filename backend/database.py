import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_merchant_db")


if not DB_PASSWORD:
    raise ValueError(
        "DB_PASSWORD was not found in .env"
    )


# =========================================================
# BUILD DATABASE URL SAFELY
# =========================================================
#
# URL.create() handles special characters such as:
# @  :  /  #  ?
# inside the password correctly.
#

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME
)


# =========================================================
# DATABASE ENGINE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


# =========================================================
# DATABASE SESSION
# =========================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# =========================================================
# BASE MODEL
# =========================================================

Base = declarative_base()


# =========================================================
# DATABASE SESSION HELPER
# =========================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()