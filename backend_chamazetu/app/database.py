from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from decouple import config

DB_HOST = config('DB_HOST')
DB_PORT = config('DB_PORT')
DB_USER = config('DB_USER')
DB_PASSWORD = config('DB_PASSWORD')
DB_NAME = config('DB_NAME')

sqlalchemy_url = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
engine = create_engine(sqlalchemy_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()