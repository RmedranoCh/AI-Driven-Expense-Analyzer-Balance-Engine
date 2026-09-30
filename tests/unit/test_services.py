import pytest
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from expense_analyzer.database import session as db_session
from expense_analyzer.database.models import DBGasto, DBPresupuestoTope
from expense_analyzer.database.session import get_session
from expense_analyzer.dashboard import services


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_session, "APP_ROOT", str(tmp_path))
    monkeypatch.setattr(
        db_session, "LOCAL_DB_PATH", str(tmp_path / "data" / "expenses.db")
    )
    db_session.reset_database_cache()
    db_session.initialize_database()
    yield
    db_session.reset_database_cache()


class TestDemoSeed:
    def test_siembra_todas_las_facturas_marcadas_demo(self):
        creadas = services.seed_demo_data("u1")
        assert creadas == len(services.DEMO_INVOICE_SOURCES)
        with get_session() as db:
            demo = db.query(func.count(DBGasto.id)).filter(DBGasto.user_id == "u1").scalar()
        assert demo == creadas

    def test_demo_no_cuenta_para_el_limite(self):
        services.seed_demo_data("u1")
        assert services.count_user_invoices("u1") == 0
        assert services.count_user_invoices("u1", include_demo=True) == len(
            services.DEMO_INVOICE_SOURCES
        )

    def test_demo_siembra_topes(self):
        services.seed_demo_data("u1")
        with get_session() as db:
            topes = db.query(DBPresupuestoTope).filter_by(user_id="u1").all()
        assert len(topes) == len(services.DEMO_TOPES)

    def test_fechas_repartidas_en_varios_meses(self):
        services.seed_demo_data("u1")
        with get_session() as db:
            fechas = [
                f[0]
                for f in db.query(DBGasto.fecha).filter_by(user_id="u1").all()
            ]
        periodos = {(f.year, f.month) for f in fechas}
        assert len(periodos) > 1
        hoy = services.utc_now().date()
        assert any(f.year == hoy.year and f.month == hoy.month for f in fechas)

    def test_restablecer_limpia_datos_previos(self):
        services.seed_demo_data("u1")
        guardado = services.save_approved_invoice(
            "u1", "Proveedor X", date.today(), [
                {"descripcion": "A", "cantidad": "1", "precio_unitario": "10", "categoria": "Otros"}
            ], Decimal("10.00"),
        )
        services.seed_demo_data("u1")
        with get_session() as db:
            assert db.query(DBGasto).filter_by(numero_comprobante=guardado).first() is None


class TestLimiteDeFacturas:
    def test_factura_real_cuenta(self):
        services.seed_demo_data("u1")
        services.save_approved_invoice(
            "u1", "Proveedor X", date.today(), [
                {"descripcion": "A", "cantidad": "1", "precio_unitario": "10", "categoria": "Otros"}
            ], Decimal("10.00"),
        )
        assert services.count_user_invoices("u1") == 1

    def test_usuario_nuevo_puede_subir_su_cuota_completa(self, monkeypatch):
        monkeypatch.setenv("MAX_INVOICES_PER_USER", "2")
        services.seed_demo_data("u1")
        for i in range(2):
            services.save_approved_invoice(
                "u1", f"P{i}", date.today(), [
                    {"descripcion": "A", "cantidad": "1", "precio_unitario": "10", "categoria": "Otros"}
                ], Decimal("10.00"),
            )
        assert services.count_user_invoices("u1") == 2


class TestComprobanteUnico:
    def test_numero_distinto_aunque_se_genere_seguido(self):
        numeros = {services.generar_numero_comprobante() for _ in range(300)}
        assert len(numeros) == 300

    def test_no_colisiona_dos_facturas_en_el_mismo_segundo(self):
        items = [
            {"descripcion": "A", "cantidad": "1", "precio_unitario": "10", "categoria": "Otros"}
        ]
        for _ in range(5):
            services.save_approved_invoice("u1", "P", date.today(), items, Decimal("10.00"))
        assert services.count_user_invoices("u1") == 5

    def test_mismo_usuario_mismo_comprobante_falla(self):
        with get_session() as db:
            db.add(DBGasto(user_id="u1", numero_comprobante="DUP", proveedor="P", total_gasto=Decimal("1.00")))
            db.commit()
        with pytest.raises(IntegrityError):
            with get_session() as db:
                db.add(DBGasto(user_id="u1", numero_comprobante="DUP", proveedor="Q", total_gasto=Decimal("2.00")))
                db.commit()


class TestSaveApprovedInvoice:
    def test_devuelve_numero_y_no_es_demo(self):
        numero = services.save_approved_invoice(
            "u1", "Proveedor", date.today(), [
                {"descripcion": "A", "cantidad": "2", "precio_unitario": "5.25", "categoria": "Cloud"}
            ], Decimal("10.50"),
        )
        assert numero.startswith("EXP-")
        with get_session() as db:
            gasto = db.query(DBGasto).filter_by(numero_comprobante=numero).first()
        assert gasto.es_demo is False
        assert gasto.total_gasto == Decimal("10.50")

    def test_recalcula_total_si_viene_cero(self):
        numero = services.save_approved_invoice(
            "u1", "P", date.today(), [
                {"descripcion": "A", "cantidad": "3", "precio_unitario": "1.50", "categoria": "Otros"}
            ], Decimal("0"),
        )
        with get_session() as db:
            gasto = db.query(DBGasto).filter_by(numero_comprobante=numero).first()
        assert gasto.total_gasto == Decimal("4.50")

    def test_items_vacios_lanza_value_error(self):
        with pytest.raises(ValueError, match="sin items"):
            services.save_approved_invoice("u1", "P", date.today(), [], Decimal("0"))

    def test_categoria_faltante_usa_la_por_defecto(self):
        numero = services.save_approved_invoice(
            "u1", "P", date.today(), [
                {"descripcion": "A", "cantidad": "1", "precio_unitario": "2"}
            ], Decimal("2.00"),
        )
        with get_session() as db:
            gasto = db.query(DBGasto).filter_by(numero_comprobante=numero).first()
            categoria = gasto.items[0].categoria
        assert categoria == "Otros"


class TestTopes:
    def test_guardar_y_cargar_topes(self):
        services.save_budget_topes("u1", {"Cloud": 500, "SaaS": Decimal("99.99")})
        cargados = services.load_budget_topes("u1", ["Cloud", "SaaS"])
        assert cargados["Cloud"] == 500.0
        assert cargados["SaaS"] == 99.99

    def test_categorias_sin_tope_toman_valor_por_defecto(self):
        cargados = services.load_budget_topes("u1", ["Nueva"])
        assert cargados["Nueva"] == services.TOPE_MENSUAL_POR_DEFECTO


class TestBuildPendingPayload:
    def test_marca_categoria_por_indice(self):
        raw = {
            "proveedor": "P",
            "fecha": "2026-01-01",
            "items": [
                {"descripcion": "A", "cantidad": "1", "precio_unitario": "10"},
            ],
        }
        payload = services.build_pending_payload(raw, ["Cloud"])
        assert payload["items"][0]["categoria"] == "Cloud"
        assert payload["total_ia"] == 10.0

    def test_sin_categorias_usa_la_por_defecto(self):
        raw = {
            "proveedor": "P",
            "fecha": None,
            "items": [{"descripcion": "A", "cantidad": "1", "precio_unitario": "10"}],
        }
        payload = services.build_pending_payload(raw, [])
        assert payload["items"][0]["categoria"] == "Otros"
