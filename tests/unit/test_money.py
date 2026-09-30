from decimal import Decimal

import pytest

from expense_analyzer.money import (
    invoice_total,
    line_total,
    to_cantidad,
    to_decimal,
    to_money,
)


class TestToMoney:
    def test_cuantiza_a_dos_decimales(self):
        assert to_money("1.005") == Decimal("1.01")
        assert to_money("1.004") == Decimal("1.00")

    def test_redondeo_half_up_no_banker(self):
        assert to_money("2.345") == Decimal("2.35")
        assert to_money("2.355") == Decimal("2.36")

    def test_suma_de_float_sin_error_binario(self):
        assert to_money(0.1) + to_money(0.2) == Decimal("0.30")

    def test_tres_veces_punto_uno(self):
        total = sum(to_money("0.1") for _ in range(3))
        assert total == Decimal("0.30")

    def test_numpy_float64(self):
        np = pytest.importorskip("numpy")
        assert to_money(np.float64("19.99")) == Decimal("19.99")
        assert to_money(np.float64(0.0)) == Decimal("0.00")

    def test_numpy_float32(self):
        np = pytest.importorskip("numpy")
        assert to_money(np.float32("7.5")) == Decimal("7.50")

    def test_numpy_int64(self):
        np = pytest.importorskip("numpy")
        assert to_money(np.int64(42)) == Decimal("42.00")

    def test_nan_y_none_a_cero(self):
        assert to_money(None) == Decimal("0.00")
        assert to_money("") == Decimal("0.00")

    def test_texto_con_simbolos(self):
        assert to_money("$ 1,234.56") == Decimal("1234.56")

    def test_decimal_passthrough(self):
        assert to_money(Decimal("9.999")) == Decimal("10.00")


class TestToDecimal:
    def test_bool(self):
        assert to_decimal(True) == Decimal("1")
        assert to_decimal(False) == Decimal("0")

    def test_separador_de_miles_decimales(self):
        assert to_decimal("1.234,56") == Decimal("1234.56")

    def test_formato_ingles(self):
        assert to_decimal("1,234.56") == Decimal("1234.56")

    def test_solo_coma_decimal(self):
        assert to_decimal("1234,5") == Decimal("1234.5")

    def test_texto_invalido_a_cero(self):
        assert to_decimal("no-es-numero") == Decimal("0")


class TestCantidad:
    def test_cuantiza_a_cuatro_decimales(self):
        assert to_cantidad("1.23456") == Decimal("1.2346")


class TestLineTotal:
    def test_precision_exacta(self):
        assert line_total("4", "15.25") == Decimal("61.00")

    def test_fraccion(self):
        assert line_total("2.5", "10.00") == Decimal("25.00")

    def test_tres_decimales_en_precio(self):
        assert line_total("3", "1.234") == Decimal("3.70")


class TestInvoiceTotal:
    def test_suma_lineas(self):
        items = [
            {"cantidad": "2", "precio_unitario": "245.50"},
            {"cantidad": "1", "precio_unitario": "89.99"},
        ]
        assert invoice_total(items) == Decimal("580.99")

    def test_lista_vacia(self):
        assert invoice_total([]) == Decimal("0.00")

    def test_ignora_campos_faltantes(self):
        assert invoice_total([{"cantidad": "1"}]) == Decimal("0.00")
