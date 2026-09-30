import os
import threading

import pytest
from sqlalchemy import inspect

from expense_analyzer.database import session as db_session
from expense_analyzer.database.session import Base, get_session


@pytest.fixture(autouse=True)
def isolated_engine(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_session, "APP_ROOT", str(tmp_path))
    monkeypatch.setattr(db_session, "LOCAL_DB_PATH", str(tmp_path / "data" / "expenses.db"))
    db_session.reset_database_cache()
    yield
    db_session.reset_database_cache()


class TestNormalizacionUrlSqlite:
    def test_ruta_relativa_se_resuelve_contra_app_root(self, tmp_path):
        url = "sqlite:///data/nested/dir/app.db"
        esperado = f"sqlite:///{tmp_path / 'data' / 'nested' / 'dir' / 'app.db'}".replace(
            os.sep, "/"
        )
        assert db_session._ensure_sqlite_directory(url) == esperado

    def test_crea_directorios_inexistentes(self, tmp_path):
        db_session._ensure_sqlite_directory("sqlite:///data/nuevo/sub/app.db")
        assert os.path.isdir(str(tmp_path / "data" / "nuevo" / "sub"))

    def test_ruta_absoluta_se_respeta(self, tmp_path):
        destino = str(tmp_path / "abs" / "app.db").replace(os.sep, "/")
        assert db_session._ensure_sqlite_directory(f"sqlite:///{destino}") == f"sqlite:///{destino}"

    def test_url_no_sqlite_no_se_toca(self):
        url = "postgresql://user:pass@host:5432/db"
        assert db_session._ensure_sqlite_directory(url) == url

    def test_memoria_no_genera_ruta(self):
        assert db_session._ensure_sqlite_directory("sqlite://") == "sqlite://"


class TestOcultamientoDeCredenciales:
    def test_oculta_password(self):
        assert db_session._redact_url("postgresql://user:secreto@host:5432/db") == (
            "postgresql://user:***@host:5432/db"
        )

    def test_url_sin_password_se_respeta(self):
        url = "postgresql://user@host:5432/db"
        assert db_session._redact_url(url) == url

    def test_url_sin_credenciales_se_respeta(self):
        assert db_session._redact_url("sqlite:///data/app.db") == "sqlite:///data/app.db"


class TestDeteccionMemoria:
    def test_archivo_no_es_memoria(self):
        assert db_session._is_memory_db("sqlite:///data/expenses.db") is False

    def test_ruta_absoluta_no_es_memoria(self):
        assert db_session._is_memory_db("sqlite:////var/lib/app.db") is False

    def test_memoria_explicita(self):
        assert db_session._is_memory_db("sqlite:///:memory:") is True

    def test_memoria_con_query(self):
        assert db_session._is_memory_db("sqlite:///:memory:?cache=shared") is True

    def test_sqlite_sin_ruta(self):
        assert db_session._is_memory_db("sqlite://") is True

    def test_motor_archivo_activa_wal(self):
        db_session.initialize_database()
        with db_session.get_engine().connect() as conn:
            journal = conn.execute(db_session.text("PRAGMA journal_mode")).scalar()
        assert str(journal).lower() == "wal"


class TestInitializeDatabase:
    def test_crea_todas_las_tablas(self):
        db_session.initialize_database()
        tablas = set(inspect(db_session.get_engine()).get_table_names())
        assert {"gastos", "gasto_items", "presupuesto_topes"} <= tablas

    def test_es_idempotente(self):
        db_session.initialize_database()
        db_session.initialize_database()
        assert len(inspect(db_session.get_engine()).get_table_names()) == 3

    def test_no_falla_con_hilos_concurrentes(self):
        errores = []

        def worker():
            try:
                db_session.initialize_database()
                with get_session() as db:
                    db.execute(db_session.text("SELECT 1"))
            except Exception as exc:
                errores.append(repr(exc))

        hilos = [threading.Thread(target=worker) for _ in range(20)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert errores == []
        assert db_session._schema_ready is True

    def test_usa_sqlite_cuando_no_hay_url(self):
        db_session.initialize_database()
        assert db_session._using_sqlite is True
        assert db_session.get_fallback_reason() is None
        assert os.path.exists(db_session.LOCAL_DB_PATH)


class TestFallbackDeBaseDeDatos:
    def test_cae_a_sqlite_si_la_url_no_responde(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:59999/db")
        monkeypatch.setattr(db_session, "CONNECTION_ATTEMPTS", 1)
        monkeypatch.setattr(db_session, "CONNECTION_BACKOFF_SECONDS", 0)
        db_session.reset_database_cache()

        engine = db_session.get_engine()

        assert engine.url.get_backend_name() == "sqlite"
        assert db_session._using_sqlite is True
        assert "no responde" in db_session.get_fallback_reason()

    def test_cae_a_sqlite_si_falta_el_driver(self, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+psycopg2://user:pass@127.0.0.1:59999/db"
        )
        db_session.reset_database_cache()

        assert db_session.get_engine().url.get_backend_name() == "sqlite"

    def test_usa_url_valida_cuando_responde(self, monkeypatch, tmp_path):
        valida = f"sqlite:///{tmp_path / 'externa.db'}"
        monkeypatch.setenv("DATABASE_URL", valida)
        db_session.reset_database_cache()

        db_session.initialize_database()

        assert db_session.get_fallback_reason() is None
        assert str(db_session.get_engine().url).endswith("externa.db")
        assert os.path.exists(str(tmp_path / "externa.db"))


class TestErrorDeEsquema:
    def test_falla_si_no_hay_modelos_registrados(self, monkeypatch):
        monkeypatch.setattr(Base.metadata, "tables", {})
        with pytest.raises(db_session.DatabaseUnavailableError):
            db_session.initialize_database()
