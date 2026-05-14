import pytest
from decimal import Decimal
import pandas as pd

def consolidar_gastos_logica(dataframe_base: pd.DataFrame) -> pd.DataFrame:
    if dataframe_base.empty:
        return pd.DataFrame(columns=["Concepto", "Categoría", "Proveedor", "Repeticiones", "Cantidad_Acumulada", "Monto_Total_Gastado"])
    return dataframe_base.groupby(["Concepto", "Categoría", "Proveedor"]).agg(
        Repeticiones=("Total ($)", "count"),
        Cantidad_Acumulada=("Cantidad", "sum"),
        Monto_Total_Gastado=("Total ($)", "sum")
    ).reset_index()

def test_calculo_linea_gasto_exacto():
    cantidad = Decimal("4")
    precio_u = Decimal("15.25")
    total = (cantidad * precio_u).quantize(Decimal("0.01"))
    assert total == Decimal("61.00")

def test_algoritmo_consolidacion_duplicados():
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