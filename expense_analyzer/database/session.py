import os
import time
import threading
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from contextlib import contextmanager

def _get_database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:
        return st.secrets.get("DATABASE_URL", None)
    except (KeyError, FileNotFoundError):
        return None

DATABASE_URL = _get_database_url()
Base = declarative_base()

_engine = None
_SessionLocal = None
_using_sqlite = False
_sqlite_lock = threading.Lock()

def get_engine():
    global _engine, _using_sqlite
    if _engine:
        return _engine

    if DATABASE_URL:
        _using_sqlite = False
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        for i in range(5):
            try:
                with _engine.connect() as conn:
                    return _engine
            except OperationalError:
                time.sleep(5)
        raise Exception("No se pudo conectar a la DB.")
    else:
        _using_sqlite = True
        db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "expenses.db")
        _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    return _engine

@contextmanager
def get_session():
    global _SessionLocal, _using_sqlite
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    if _using_sqlite:
        _sqlite_lock.acquire()

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if _using_sqlite:
            _sqlite_lock.release()