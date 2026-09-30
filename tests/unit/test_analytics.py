import pandas as pd

from expense_analyzer.analytics import (
    COLUMNAS_CONSOLIDADAS,
    COLUMNAS_DETALLE,
    consolidar_gastos,
    gasto_por_categoria,
    gasto_por_proveedor,
    resumen_mensual,
)


def _df(datos):
    return pd.DataFrame(datos, columns=COLUMNAS_DETALLE)


class TestConsolidarGastos:
    def test_agrupa_duplicados(self):
        df = _df(
            [
                {"Concepto": "Instancia AWS", "Categoría": "Cloud", "Proveedor": "Amazon", "Cantidad": 1.0, "Total ($)": 30.0},
                {"Concepto": "Instancia AWS", "Categoría": "Cloud", "Proveedor": "Amazon", "Cantidad": 1.0, "Total ($)": 30.0},
                {"Concepto": "Notion", "Categoría": "SaaS", "Proveedor": "Notion Labs", "Cantidad": 2.0, "Total ($)": 20.0},
            ]
        )
        res = consolidar_gastos(df)
        aws = res[res["Concepto"] == "Instancia AWS"].iloc[0]
        assert aws["Repeticiones"] == 2
        assert aws["Cantidad_Acumulada"] == 2.0
        assert aws["Monto_Total_Gastado"] == 60.0
        assert len(res) == 2

    def test_ordena_por_monto_descendente(self):
        df = _df(
            [
                {"Concepto": "A", "Categoría": "X", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 10.0},
                {"Concepto": "B", "Categoría": "X", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 99.0},
            ]
        )
        res = consolidar_gastos(df)
        assert list(res["Concepto"]) == ["B", "A"]

    def test_vacio_devuelve_columnas(self):
        res = consolidar_gastos(pd.DataFrame(columns=COLUMNAS_DETALLE))
        assert list(res.columns) == COLUMNAS_CONSOLIDADAS
        assert res.empty


class TestResumenMensual:
    def test_agrupa_por_mes(self):
        df = _df(
            [
                {"Concepto": "A", "Categoría": "X", "Proveedor": "P", "Fecha": "2026-01-10", "Cantidad": 1.0, "Total ($)": 10.0},
                {"Concepto": "B", "Categoría": "X", "Proveedor": "P", "Fecha": "2026-01-20", "Cantidad": 1.0, "Total ($)": 15.0},
                {"Concepto": "C", "Categoría": "X", "Proveedor": "P", "Fecha": "2026-02-01", "Cantidad": 1.0, "Total ($)": 7.0},
            ]
        )
        res = resumen_mensual(df)
        assert list(res["Mes_Periodo"]) == ["2026-01", "2026-02"]
        assert res.iloc[0]["Total ($)"] == 25.0

    def test_vacio(self):
        assert resumen_mensual(pd.DataFrame(columns=COLUMNAS_DETALLE)).empty


class TestAgrupaciones:
    def test_por_categoria(self):
        df = _df(
            [
                {"Concepto": "A", "Categoría": "Cloud", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 10.0},
                {"Concepto": "B", "Categoría": "Cloud", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 5.0},
                {"Concepto": "C", "Categoría": "SaaS", "Proveedor": "P", "Cantidad": 1.0, "Total ($)": 3.0},
            ]
        )
        res = gasto_por_categoria(df).set_index("Categoría")["Total ($)"].to_dict()
        assert res == {"Cloud": 15.0, "SaaS": 3.0}

    def test_por_proveedor(self):
        df = _df(
            [
                {"Concepto": "A", "Categoría": "X", "Proveedor": "AWS", "Cantidad": 1.0, "Total ($)": 10.0},
                {"Concepto": "B", "Categoría": "X", "Proveedor": "GCP", "Cantidad": 1.0, "Total ($)": 4.0},
            ]
        )
        res = gasto_por_proveedor(df).set_index("Proveedor")["Total ($)"].to_dict()
        assert res == {"AWS": 10.0, "GCP": 4.0}
