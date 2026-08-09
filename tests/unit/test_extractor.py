import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


@pytest.fixture
def extractor():
    with patch("expense_analyzer.ai.extractor.get_groq_key", return_value="key"):
        with patch("expense_analyzer.ai.extractor.Groq"):
            from expense_analyzer.ai.extractor import InvoiceExtractor
            return InvoiceExtractor()


class TestSanitizeJsonData:
    def test_standard_case(self, extractor):
        result = extractor._sanitize_json_data({
            "proveedor": "Test Corp",
            "fecha": "2024-01-15",
            "items": [
                {"descripcion": "Item 1", "cantidad": 2, "precio_unitario": 10.50}
            ]
        })
        assert result["proveedor"] == "Test Corp"
        assert result["fecha"] == "2024-01-15"
        assert len(result["items"]) == 1
        assert result["items"][0]["descripcion"] == "Item 1"
        assert result["items"][0]["cantidad"] == Decimal("2")
        assert result["items"][0]["precio_unitario"] == Decimal("10.50")

    def test_missing_proveedor_falls_back_to_cliente(self, extractor):
        result = extractor._sanitize_json_data({
            "cliente": "Cliente SA",
            "fecha": None,
            "items": []
        })
        assert result["proveedor"] == "Cliente SA"

    def test_missing_all_fields_uses_defaults(self, extractor):
        result = extractor._sanitize_json_data({})
        assert result["proveedor"] == "Desconocido"
        assert result["fecha"] is None
        assert result["items"] == []

    def test_items_missing_fields_uses_defaults(self, extractor):
        result = extractor._sanitize_json_data({
            "proveedor": "X",
            "items": [{}]
        })
        assert result["items"][0]["descripcion"] == "Concepto General"
        assert result["items"][0]["cantidad"] == Decimal("1")
        assert result["items"][0]["precio_unitario"] == Decimal("0")

    @pytest.mark.parametrize("input_date,expected", [
        ("2024-01-15", "2024-01-15"),
        ("15/01/2024", "2024-01-15"),
        ("15-01-2024", "2024-01-15"),
        ("2024/01/15", "2024-01-15"),
        ("15/01/24", "2024-01-15"),
        ("", None),
        (None, None),
        ("null", None),
        ("invalido", None),
    ])
    def test_date_parsing_various_formats(self, extractor, input_date, expected):
        result = extractor._sanitize_json_data({
            "proveedor": "X",
            "fecha": input_date,
            "items": []
        })
        assert result["fecha"] == expected

    @pytest.mark.parametrize("raw,expected", [
        ("$10.50", Decimal("10.50")),
        ("1,234.56", Decimal("1234.56")),
        ("$ 99.99", Decimal("99.99")),
        ("0", Decimal("0")),
        (None, Decimal("0.00")),
        ("abc", Decimal("0.00")),
    ])
    def test_decimal_sanitization(self, extractor, raw, expected):
        result = extractor._sanitize_json_data({
            "proveedor": "X",
            "items": [{"cantidad": raw, "precio_unitario": raw}]
        })
        assert result["items"][0]["cantidad"] == expected
        assert result["items"][0]["precio_unitario"] == expected

    def test_empty_items_list(self, extractor):
        result = extractor._sanitize_json_data({
            "proveedor": "X",
            "items": []
        })
        assert result["items"] == []

    def test_multiple_items(self, extractor):
        result = extractor._sanitize_json_data({
            "proveedor": "X",
            "items": [
                {"descripcion": "A", "cantidad": 1, "precio_unitario": 10},
                {"descripcion": "B", "cantidad": 2, "precio_unitario": 20},
            ]
        })
        assert len(result["items"]) == 2
        assert result["items"][1]["cantidad"] == Decimal("2")