import pandas as pd

COLUMNAS_DETALLE = [
    "Comprobante",
    "Proveedor",
    "Fecha",
    "Concepto",
    "Cantidad",
    "Precio U. ($)",
    "Total ($)",
    "Categoría",
]

COLUMNAS_CONSOLIDADAS = [
    "Concepto",
    "Categoría",
    "Proveedor",
    "Repeticiones",
    "Cantidad_Acumulada",
    "Monto_Total_Gastado",
]

COLUMNAS_CABECERA = [
    "id_db",
    "Comprobante",
    "Proveedor",
    "Fecha",
    "Total Gasto ($)",
]


def consolidar_gastos(df_detalle: pd.DataFrame) -> pd.DataFrame:
    if df_detalle.empty:
        return pd.DataFrame(columns=COLUMNAS_CONSOLIDADAS)
    return (
        df_detalle.groupby(["Concepto", "Categoría", "Proveedor"])
        .agg(
            Repeticiones=("Total ($)", "count"),
            Cantidad_Acumulada=("Cantidad", "sum"),
            Monto_Total_Gastado=("Total ($)", "sum"),
        )
        .reset_index()
        .sort_values(by="Monto_Total_Gastado", ascending=False)
    )


def resumen_mensual(df_detalle: pd.DataFrame) -> pd.DataFrame:
    if df_detalle.empty:
        return pd.DataFrame(columns=["Mes_Periodo", "Total ($)"])
    con_periodo = df_detalle.copy()
    con_periodo["Mes_Periodo"] = (
        pd.to_datetime(con_periodo["Fecha"], errors="coerce")
        .dt.to_period("M")
        .astype(str)
    )
    con_periodo = con_periodo.dropna(subset=["Mes_Periodo"])
    con_periodo = con_periodo[con_periodo["Mes_Periodo"] != "NaT"]
    if con_periodo.empty:
        return pd.DataFrame(columns=["Mes_Periodo", "Total ($)"])
    return (
        con_periodo.groupby("Mes_Periodo")["Total ($)"]
        .sum()
        .reset_index()
        .sort_values(by="Mes_Periodo")
    )


def gasto_por_categoria(df_detalle: pd.DataFrame) -> pd.DataFrame:
    if df_detalle.empty:
        return pd.DataFrame(columns=["Categoría", "Total ($)"])
    return df_detalle.groupby("Categoría")["Total ($)"].sum().reset_index()


def gasto_por_proveedor(df_detalle: pd.DataFrame) -> pd.DataFrame:
    if df_detalle.empty:
        return pd.DataFrame(columns=["Proveedor", "Total ($)"])
    return df_detalle.groupby("Proveedor")["Total ($)"].sum().reset_index()
