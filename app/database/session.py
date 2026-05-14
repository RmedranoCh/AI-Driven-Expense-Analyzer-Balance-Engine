import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base()

_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine:
        return _engine
        
    _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    intentos = 5
    for i in range(intentos):
        try:
            with _engine.connect() as conn:
                return _engine
        except OperationalError:
            time.sleep(5)
    raise Exception("❌ No se pudo conectar a la DB.")

def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()
