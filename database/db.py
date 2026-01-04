from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import os
load_dotenv()

class Base(DeclarativeBase):
    pass

engine = create_engine(os.getenv("DATABASE_DEVELOPMENT_URI"), echo=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
