import os
import time
import logging
import threading
import streamlit as st
from streamlit.errors import StreamlitAPIException
from sqlalchemy import Boolean, Integer, Numeric, create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from contextlib import contextmanager

logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_DB_PATH = os.path.join(APP_ROOT, "data", "expenses.db")

CONNECTION_ATTEMPTS = 5
CONNECTION_BACKOFF_SECONDS = 2
DDL_ATTEMPTS = 5
DDL_BACKOFF_SECONDS = 2
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_POOL_TIMEOUT_SECONDS = 60


class DatabaseUnavailableError(RuntimeError):
    pass


def _get_database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:
        return st.secrets.get("DATABASE_URL", None)
    except (KeyError, FileNotFoundError, StreamlitAPIException):
        return None


def _redact_url(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host = rest.rsplit("@", 1)
    if ":" not in credentials:
        return url
    return f"{scheme}://{credentials.split(':')[0]}:***@{host}"


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_memory_db(url: str) -> bool:
    return url.endswith(":memory:") or url.endswith("")


def _ensure_sqlite_directory(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw_path = url[len(prefix):]
    if not raw_path:
        return url
    db_path = raw_path if raw_path.startswith("/") else os.path.join(APP_ROOT, raw_path)
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return f"{prefix}{db_path.replace(os.sep, '/')}"


def _build_sqlite_engine(url: str):
    connect_args = {
        "check_same_thread": False,
        "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
    }
    memory_db = _is_memory_db(url)
    if memory_db:
        pool_kwargs = {"poolclass": StaticPool}
    else:
        pool_kwargs = {
            "poolclass": QueuePool,
            "pool_size": 1,
            "max_overflow": 0,
            "pool_timeout": SQLITE_POOL_TIMEOUT_SECONDS,
        }

    engine = create_engine(url, connect_args=connect_args, **pool_kwargs)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
            if not memory_db:
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA synchronous = NORMAL")
        finally:
            cursor.close()

    return engine


def _build_engine_for_url(url: str):
    if _is_sqlite(url):
        return _build_sqlite_engine(url)
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def _verify_connection(engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Conexion fallida con la base de datos: %s", exc)
        return False


def _connect_configured_database(url: str):
    for attempt in range(1, CONNECTION_ATTEMPTS + 1):
        try:
            engine = _build_engine_for_url(url)
        except Exception as exc:
            logger.error(
                "No se pudo crear el engine para %s: %s", _redact_url(url), exc
            )
            return None
        if _verify_connection(engine):
            return engine
        engine.dispose()
        logger.warning(
            "Intento %s/%s sin conexion a la base de datos configurada.",
            attempt,
            CONNECTION_ATTEMPTS,
        )
        time.sleep(CONNECTION_BACKOFF_SECONDS * attempt)
    return None


def _build_local_sqlite_engine():
    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    return _build_sqlite_engine(f"sqlite:///{LOCAL_DB_PATH}")


def _resolve_engine():
    url = _get_database_url()
    if url:
        normalized = _ensure_sqlite_directory(url) if _is_sqlite(url) else url
        engine = _connect_configured_database(normalized)
        if engine is not None:
            return engine, _is_sqlite(normalized), None
        logger.error(
            "DATABASE_URL (%s) no disponible, se usara SQLite local en data/expenses.db.",
            _redact_url(normalized),
        )
        return (
            _build_local_sqlite_engine(),
            True,
            "La base de datos configurada en DATABASE_URL no responde; "
            "se activo el almacenamiento local temporal.",
        )
    return _build_local_sqlite_engine(), True, None


DATABASE_URL = _get_database_url()
Base = declarative_base()

_engine = None
_SessionLocal = None
_using_sqlite = False
_fallback_reason = None
_engine_lock = threading.Lock()
_sqlite_lock = threading.RLock()
_schema_lock = threading.Lock()
_schema_ready = False


def get_engine():
    global _engine, _using_sqlite, _fallback_reason
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        _engine, _using_sqlite, _fallback_reason = _resolve_engine()
        return _engine


def get_fallback_reason():
    get_engine()
    return _fallback_reason


def reset_database_cache() -> None:
    global _engine, _SessionLocal, _using_sqlite, _fallback_reason, _schema_ready
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _SessionLocal = None
        _using_sqlite = False
        _fallback_reason = None
        _schema_ready = False


def _default_para(columna) -> str:
    if isinstance(columna.type, Boolean):
        return "false"
    if isinstance(columna.type, (Numeric, Integer)):
        return "0"
    return "''"


def _add_missing_columns(engine) -> None:
    inspector = inspect(engine)
    dialect = engine.dialect
    for tabla in Base.metadata.sorted_tables:
        if not inspector.has_table(tabla.name):
            continue
        existentes = {col["name"] for col in inspector.get_columns(tabla.name)}
        for columna in tabla.columns:
            if columna.name in existentes:
                continue
            partes = [
                f'ALTER TABLE "{tabla.name}" ADD COLUMN "{columna.name}" '
                f"{columna.type.compile(dialect=dialect)}"
            ]
            if not columna.nullable:
                partes.append(f"DEFAULT {_default_para(columna)} NOT NULL")
            elif columna.server_default is None and isinstance(
                columna.type, (Boolean, Numeric)
            ):
                partes.append(f"DEFAULT {_default_para(columna)}")
            sentencia = " ".join(partes)
            logger.info("Migracion de esquema: %s", sentencia)
            with engine.begin() as conn:
                conn.execute(text(sentencia))


def initialize_database() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        from expense_analyzer.database import models

        if not Base.metadata.tables:
            raise DatabaseUnavailableError(
                "No se detectaron tablas en los modelos de datos: "
                f"el modulo '{models.__name__}' no registro ninguna."
            )
        engine = get_engine()
        for attempt in range(1, DDL_ATTEMPTS + 1):
            try:
                Base.metadata.create_all(bind=engine, checkfirst=True)
                _add_missing_columns(engine)
                _schema_ready = True
                return
            except OperationalError as exc:
                logger.warning(
                    "No se pudo crear el esquema (intento %s/%s): %s",
                    attempt,
                    DDL_ATTEMPTS,
                    exc,
                )
                engine.dispose()
                time.sleep(DDL_BACKOFF_SECONDS * attempt)
        raise DatabaseUnavailableError(
            "No se pudo preparar la base de datos tras varios intentos. "
            "Si configuraste DATABASE_URL, verifica que el servidor este "
            "vigente y que el driver correspondiente este en requirements.txt."
        )


@contextmanager
def get_session():
    global _SessionLocal
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
