import pytest
from decimal import Decimal
import pandas as pd


def consolidar_gastos_logica(dataframe_base: pd.DataFrame) -> pd.DataFrame:
    if dataframe_base.empty:
        return pd.DataFrame(columns=[
            "Concepto", "Categoría", "Proveedor",
            "Repeticiones", "Cantidad_Acumulada", "Monto_Total_Gastado"
        ])
    return dataframe_base.groupby(["Concepto", "Categoría", "Proveedor"]).agg(
        Repeticiones=("Total ($)", "count"),
        Cantidad_Acumulada=("Cantidad", "sum"),
        Monto_Total_Gastado=("Total ($)", "sum")
    ).reset_index()


class TestCalculoLineaGasto:
    def test_exacto(self):
        cantidad = Decimal("4")
        precio_u = Decimal("15.25")
        total = (cantidad * precio_u).quantize(Decimal("0.01"))
        assert total == Decimal("61.00")

    def test_con_fracciones(self):
        cantidad = Decimal("2.5")
        precio_u = Decimal("10.00")
        total = (cantidad * precio_u).quantize(Decimal("0.01"))
        assert total == Decimal("25.00")

    def test_grandes_cantidades(self):
        cantidad = Decimal("1000")
        precio_u = Decimal("999.99")
        total = (cantidad * precio_u).quantize(Decimal("0.01"))
        assert total == Decimal("999990.00")

    def test_precision_tres_decimales(self):
        cantidad = Decimal("3")
        precio_u = Decimal("1.234")
        total = (cantidad * precio_u).quantize(Decimal("0.01"))
        assert total == Decimal("3.70")


class TestConsolidacionDuplicados:
    def test_agrupa_duplicados(self):
        datos_mock = [
            {"Concepto": "Instancia AWS", "Categoría": "Software & SaaS", "Proveedor": "Amazon", "Cantidad": 1.0, "Total ($)": 30.0},
            {"Concepto": "Instancia AWS", "Categoría": "Software & SaaS", "Proveedor": "Amazon", "Cantidad": 1.0, "Total ($)": 30.0},
            {"Concepto": "Suscripción Notion", "Categoría": "Software & SaaS", "Proveedor": "Notion Labs", "Cantidad": 2.0, "Total ($)": 20.0}
        ]
        df_res = consolidar_gastos_logica(pd.DataFrame(datos_mock))
        aws_row = df_res[df_res["Concepto"] == "Instancia AWS"].iloc[0]
        assert aws_row["Repeticiones"] == 2
        assert aws_row["Cantidad_Acumulada"] == 2.0
        assert aws_row["Monto_Total_Gastado"] == 60.0
        assert len(df_res) == 2

    def test_empty_dataframe(self):
        df_res = consolidar_gastos_logica(pd.DataFrame())
        assert list(df_res.columns) == [
            "Concepto", "Categoría", "Proveedor",
            "Repeticiones", "Cantidad_Acumulada", "Monto_Total_Gastado"
        ]
        assert len(df_res) == 0

    def test_single_row(self):
        datos = [{"Concepto": "A", "Categoría": "X", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 10.0}]
        df_res = consolidar_gastos_logica(pd.DataFrame(datos))
        assert len(df_res) == 1
        assert df_res.iloc[0]["Monto_Total_Gastado"] == 10.0

    def test_diferentes_categorias_mismo_concepto(self):
        datos = [
            {"Concepto": "Hosting", "Categoría": "Cloud", "Proveedor": "AWS", "Cantidad": 1.0, "Total ($)": 50.0},
            {"Concepto": "Hosting", "Categoría": "On-Prem", "Proveedor": "AWS", "Cantidad": 1.0, "Total ($)": 30.0},
        ]
        df_res = consolidar_gastos_logica(pd.DataFrame(datos))
        assert len(df_res) == 2
        assert df_res["Monto_Total_Gastado"].sum() == 80.0

    def test_multiples_proveedores_mismo_concepto(self):
        datos = [
            {"Concepto": "Hosting", "Categoría": "Cloud", "Proveedor": "AWS", "Cantidad": 1.0, "Total ($)": 50.0},
            {"Concepto": "Hosting", "Categoría": "Cloud", "Proveedor": "GCP", "Cantidad": 1.0, "Total ($)": 40.0},
        ]
        df_res = consolidar_gastos_logica(pd.DataFrame(datos))
        assert len(df_res) == 2
