from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

PGBOUNCER_HOST = os.getenv("PGBOUNCER_HOST")
PGBOUNCER_PORT = os.getenv("PGBOUNCER_PORT")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

sqlalchemy_url = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{PGBOUNCER_HOST}:{PGBOUNCER_PORT}/{DB_NAME}"
)
# DATABASE_URL = "postgresql://mankindjnr:tNNhwY1XOwwQPkhL@pgbouncer:6432/chamazetudb"

engine = create_engine(sqlalchemy_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
