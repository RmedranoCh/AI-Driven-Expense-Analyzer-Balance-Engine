import pytest
from decimal import Decimal
from datetime import datetime, timezone
from expense_analyzer.database.models import DBGasto, DBGastoItem, DBPresupuestoTope


class TestDBGasto:
    def test_create_gasto(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-001",
            proveedor="Test Corp",
            total_gasto=Decimal("150.00"),
        )
        in_memory_db.add(gasto)
        in_memory_db.commit()

        saved = in_memory_db.query(DBGasto).filter_by(numero_comprobante="EXP-001").first()
        assert saved is not None
        assert saved.proveedor == "Test Corp"
        assert saved.total_gasto == Decimal("150.00")
        assert saved.user_id == "user1"

    def test_create_gasto_with_items(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-002",
            proveedor="AWS",
            total_gasto=Decimal("100.00"),
        )
        gasto.items = [
            DBGastoItem(
                descripcion="EC2 Instance",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100.00"),
                total_linea=Decimal("100.00"),
                categoria="Infraestructura Cloud & Hosting",
            )
        ]
        in_memory_db.add(gasto)
        in_memory_db.commit()

        saved = in_memory_db.query(DBGasto).filter_by(numero_comprobante="EXP-002").first()
        assert len(saved.items) == 1
        assert saved.items[0].descripcion == "EC2 Instance"
        assert saved.items[0].total_linea == Decimal("100.00")

    def test_gasto_default_fecha(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-003",
            proveedor="X",
            total_gasto=Decimal("0.00"),
        )
        in_memory_db.add(gasto)
        in_memory_db.commit()

        saved = in_memory_db.query(DBGasto).filter_by(numero_comprobante="EXP-003").first()
        assert saved.fecha is not None
        assert isinstance(saved.fecha, datetime)

    def test_cascade_delete_removes_items(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-004",
            proveedor="X",
            total_gasto=Decimal("50.00"),
        )
        gasto.items = [
            DBGastoItem(
                descripcion="Item 1",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("50.00"),
                total_linea=Decimal("50.00"),
            )
        ]
        in_memory_db.add(gasto)
        in_memory_db.commit()

        item_id = gasto.items[0].id
        in_memory_db.delete(gasto)
        in_memory_db.commit()

        assert in_memory_db.query(DBGastoItem).filter_by(id=item_id).first() is None

    def test_gasto_with_file_hash(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-005",
            proveedor="X",
            total_gasto=Decimal("10.00"),
            file_hash="abc123def456",
        )
        in_memory_db.add(gasto)
        in_memory_db.commit()

        saved = in_memory_db.query(DBGasto).filter_by(file_hash="abc123def456").first()
        assert saved is not None
        assert saved.numero_comprobante == "EXP-005"

    def test_multiple_items_same_gasto(self, in_memory_db):
        gasto = DBGasto(
            user_id="user1",
            numero_comprobante="EXP-006",
            proveedor="Dell",
            total_gasto=Decimal("3000.00"),
        )
        gasto.items = [
            DBGastoItem(descripcion="Laptop", cantidad=Decimal("1"), precio_unitario=Decimal("2500.00"), total_linea=Decimal("2500.00")),
            DBGastoItem(descripcion="Monitor", cantidad=Decimal("1"), precio_unitario=Decimal("500.00"), total_linea=Decimal("500.00")),
        ]
        in_memory_db.add(gasto)
        in_memory_db.commit()

        items = in_memory_db.query(DBGastoItem).filter(DBGastoItem.gasto_id == gasto.id).all()
        assert len(items) == 2


class TestDBPresupuestoTope:
    def test_create_tope(self, in_memory_db):
        tope = DBPresupuestoTope(
            user_id="user1",
            categoria="Infraestructura Cloud & Hosting",
            tope_mensual=Decimal("1000.00"),
        )
        in_memory_db.add(tope)
        in_memory_db.commit()

        saved = in_memory_db.query(DBPresupuestoTope).filter_by(
            user_id="user1", categoria="Infraestructura Cloud & Hosting"
        ).first()
        assert saved is not None
        assert saved.tope_mensual == Decimal("1000.00")

    def test_multiple_topes_per_user(self, in_memory_db):
        categorias = ["A", "B", "C"]
        for cat in categorias:
            in_memory_db.add(DBPresupuestoTope(user_id="user1", categoria=cat, tope_mensual=Decimal("500.00")))
        in_memory_db.commit()

        topos = in_memory_db.query(DBPresupuestoTope).filter_by(user_id="user1").all()
        assert len(topos) == 3

    def test_tope_precision(self, in_memory_db):
        tope = DBPresupuestoTope(
            user_id="user1",
            categoria="Test",
            tope_mensual=Decimal("1234.56"),
        )
        in_memory_db.add(tope)
        in_memory_db.commit()

        saved = in_memory_db.query(DBPresupuestoTope).first()
        assert saved.tope_mensual == Decimal("1234.56")


class TestDBGastoItem:
    def test_item_default_categoria(self, in_memory_db):
        gasto = DBGasto(user_id="u1", numero_comprobante="EXP-010", proveedor="X", total_gasto=Decimal("10.00"))
        item = DBGastoItem(
            descripcion="Generic",
            cantidad=Decimal("1"),
            precio_unitario=Decimal("10.00"),
            total_linea=Decimal("10.00"),
            gasto=gasto,
        )
        in_memory_db.add(gasto)
        in_memory_db.commit()

        assert item.categoria == "Otros"

    def test_item_precision_values(self, in_memory_db):
        gasto = DBGasto(user_id="u1", numero_comprobante="EXP-011", proveedor="X", total_gasto=Decimal("61.00"))
        item = DBGastoItem(
            descripcion="Test",
            cantidad=Decimal("4"),
            precio_unitario=Decimal("15.25"),
            total_linea=Decimal("61.00"),
            gasto=gasto,
        )
        in_memory_db.add(gasto)
        in_memory_db.commit()

        saved = in_memory_db.query(DBGastoItem).first()
        assert saved.cantidad == Decimal("4")
        assert saved.precio_unitario == Decimal("15.25")
        assert saved.total_linea == Decimal("61.00")
