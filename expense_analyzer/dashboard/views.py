import io
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import contains_eager

from expense_analyzer.analytics import (
    COLUMNAS_CABECERA,
    COLUMNAS_DETALLE,
    consolidar_gastos,
    gasto_por_categoria,
    gasto_por_proveedor,
    resumen_mensual,
)
from expense_analyzer.database.session import get_session
from expense_analyzer.database.models import DBGasto, DBGastoItem, utc_now
from expense_analyzer.dashboard.services import delete_gasto, save_budget_topes
from expense_analyzer.money import to_money


def _no_items_message() -> None:
    st.info("Sin registros de gastos cargados en el sistema.")


@st.cache_data(show_spinner=False)
def _reporte_excel(historial_json: str, consolidado_json: str) -> bytes:
    historial = pd.read_json(io.StringIO(historial_json), orient="split")
    consolidado = pd.read_json(io.StringIO(consolidado_json), orient="split")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        historial.to_excel(writer, index=False, sheet_name="📋 Historial Filtrado")
        consolidado.to_excel(writer, index=False, sheet_name="Balance Consolidado")
    return buffer.getvalue()


def _cargar_items(user_id: str, desde: datetime, hasta: datetime):
    with get_session() as db:
        items = (
            db.query(DBGastoItem)
            .join(DBGastoItem.gasto)
            .options(contains_eager(DBGastoItem.gasto))
            .filter(
                DBGasto.user_id == user_id,
                DBGasto.fecha >= desde,
                DBGasto.fecha <= hasta,
            )
            .all()
        )
        gastos = (
            db.query(DBGasto)
            .filter(
                DBGasto.user_id == user_id,
                DBGasto.fecha >= desde,
                DBGasto.fecha <= hasta,
            )
            .all()
        )
    return items, gastos


def render_dashboard_stats(user_id: str, fecha_inicio: date, fecha_fin: date) -> None:
    fecha_inicio_dt = datetime.combine(fecha_inicio, datetime.min.time())
    fecha_fin_dt = datetime.combine(fecha_fin, datetime.max.time())

    items_query, gastos_cabecera = _cargar_items(user_id, fecha_inicio_dt, fecha_fin_dt)

    if not items_query:
        _no_items_message()
        return

    datos_tabla = [
        {
            "Comprobante": item.gasto.numero_comprobante,
            "Proveedor": item.gasto.proveedor,
            "Fecha": item.gasto.fecha.strftime("%Y-%m-%d"),
            "Concepto": item.descripcion,
            "Cantidad": float(item.cantidad),
            "Precio U. ($)": float(item.precio_unitario),
            "Total ($)": float(item.total_linea),
            "Categoría": item.categoria,
        }
        for item in items_query
    ]

    is_admin = st.session_state.get("admin_mode", False)
    datos_cabecera_lista = (
        [
            {
                "id_db": g.id,
                "Comprobante": g.numero_comprobante,
                "Proveedor": g.proveedor,
                "Fecha": g.fecha.strftime("%Y-%m-%d %H:%M"),
                "Total Gasto ($)": float(g.total_gasto),
            }
            for g in gastos_cabecera
        ]
        if is_admin
        else []
    )

    df_base = pd.DataFrame(datos_tabla, columns=COLUMNAS_DETALLE)

    if df_base.empty:
        st.warning(
            f"No existen transacciones registradas en el rango desde {fecha_inicio} hasta {fecha_fin}."
        )
        return

    df_agrupado = consolidar_gastos(df_base)

    col1, col2, col3 = st.columns(3)
    col1.metric("Gasto Filtrado Acumulado", f"${to_money(df_base['Total ($)'].sum()):,.2f}")
    col2.metric("Conceptos Distintos en Rango", len(df_agrupado))
    col3.metric("Proveedores en Rango", df_base["Proveedor"].nunique())

    st.markdown("---")
    st.markdown("### 📈 Evolución Temporal de Salidas")
    df_mensual = resumen_mensual(df_base)

    if not df_mensual.empty:
        fig_linea = px.line(
            df_mensual,
            x="Mes_Periodo",
            y="Total ($)",
            markers=True,
            labels={
                "Mes_Periodo": "Mes de Operación",
                "Total ($)": "Egresos Consolidados ($)",
            },
        )
        fig_linea.update_layout(hovermode="x unified", template="plotly_white")
        fig_linea.update_traces(line_color="#c0392b", line_width=3, marker=dict(size=8))
        st.plotly_chart(fig_linea, width="stretch")

    st.markdown("---")

    tabs_list = [
        "📊 Conceptos Consolidados (Agrupados)",
        "Historial Filtrado",
        "📐 Participación de Rubros",
    ]
    if is_admin:
        tabs_list.append("🔥 Administrar y Purgar")
    tabs = st.tabs(tabs_list)
    tab1, tab2, tab3 = tabs[0], tabs[1], tabs[2]
    tab4 = tabs[3] if is_admin else None

    with tab1:
        st.markdown(f"### 🔄 Gastos Agrupados Automáticamente ({fecha_inicio} a {fecha_fin})")
        st.dataframe(df_agrupado, width="stretch", hide_index=True)

    with tab2:
        col_header, col_download = st.columns([4, 1])
        col_header.markdown("### 📜 Transacciones Extraídas en el Periodo")

        col_download.download_button(
            label="📥 Descargar Reporte en Excel",
            data=_reporte_excel(
                df_base.to_json(orient="split", date_format="iso"),
                df_agrupado.to_json(orient="split", date_format="iso"),
            ),
            file_name=f"balance_gastos_ia_{fecha_inicio}_{fecha_fin}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        st.dataframe(df_base, width="stretch", hide_index=True)

    with tab3:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Gastos por Categoría Financiera:**")
            fig_bar = px.bar(
                gasto_por_categoria(df_base),
                x="Categoría",
                y="Total ($)",
                text_auto=".2f",
                color="Categoría",
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_bar.update_layout(showlegend=False, template="plotly_white")
            st.plotly_chart(fig_bar, width="stretch")
        with col_g2:
            st.write("**Participación por Proveedor:**")
            fig_pie = px.pie(
                gasto_por_proveedor(df_base),
                values="Total ($)",
                names="Proveedor",
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pie, width="stretch")

    if tab4:
        with tab4:
            st.markdown("### 🗑️ Eliminación de Comprobantes Erróneos")
            st.write(
                "Selecciona una factura de la lista desplegable para borrarla por completo del balance."
            )

            if datos_cabecera_lista:
                df_cabecera = pd.DataFrame(datos_cabecera_lista, columns=COLUMNAS_CABECERA)
                opciones_selectbox = {
                    row["id_db"]: (
                        f"{row['Comprobante']} | {row['Proveedor']} | "
                        f"${row['Total Gasto ($)']:,.2f} ({row['Fecha']})"
                    )
                    for _, row in df_cabecera.iterrows()
                }

                id_seleccionado = st.selectbox(
                    "Selecciona el registro a eliminar:",
                    options=list(opciones_selectbox.keys()),
                    format_func=lambda x: opciones_selectbox[x],
                )

                st.error(
                    "⚠️ **Acción Irreversible:** Al hacer clic en borrar, se eliminará la cabecera "
                    "y todas sus líneas de concepto asociadas."
                )

                if st.button("🔥 Confirmar Eliminación Definitiva", width="stretch"):
                    try:
                        if delete_gasto(user_id, int(id_seleccionado)):
                            st.success(
                                "Registro eliminado correctamente de la base de datos."
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar el registro: {e}")
            else:
                st.info("No hay facturas registradas disponibles para purgar.")



def render_budget_alerts(user_id: str, categorias_validas: list) -> None:
    st.subheader("🚨 Control de Presupuestos Mensuales")

    now = utc_now()
    mes_actual_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if mes_actual_start.month == 12:
        mes_actual_end = mes_actual_start.replace(year=mes_actual_start.year + 1, month=1)
    else:
        mes_actual_end = mes_actual_start.replace(month=mes_actual_start.month + 1)
    mes_actual_str = now.strftime("%Y-%m")

    with get_session() as db:
        items_query = (
            db.query(DBGastoItem)
            .join(DBGastoItem.gasto)
            .options(contains_eager(DBGastoItem.gasto))
            .filter(
                DBGasto.user_id == user_id,
                DBGasto.fecha >= mes_actual_start,
                DBGasto.fecha < mes_actual_end,
            )
            .all()
        )

    df_mes_actual = pd.DataFrame(
        [
            {
                "Total ($)": float(item.total_linea),
                "Categoría": item.categoria,
                "Mes": mes_actual_str,
            }
            for item in items_query
        ],
        columns=["Total ($)", "Categoría", "Mes"],
    )

    topes_presupuesto = st.session_state.topes_presupuesto

    col_config, col_alertas = st.columns([1, 2])

    with col_config:
        st.markdown(f"**Ajustar topes mensuales ({mes_actual_str}):**")
        df_topes_input = pd.DataFrame(
            [
                {
                    "Categoría": categoria,
                    "Tope Mensual ($)": float(topes_presupuesto[categoria]),
                }
                for categoria in categorias_validas
            ]
        )

        edited_topes_df = st.data_editor(
            df_topes_input,
            width="stretch",
            hide_index=True,
            column_config={
                "Categoría": st.column_config.TextColumn("Categoría", disabled=True),
                "Tope Mensual ($)": st.column_config.NumberColumn(
                    "Tope Mensual ($)", min_value=0.0, format="$%.2f", step=10.0
                ),
            },
        )

        hubo_cambio = False
        for _, row in edited_topes_df.iterrows():
            nuevo = float(row["Tope Mensual ($)"])
            if nuevo != topes_presupuesto.get(row["Categoría"]):
                hubo_cambio = True
            topes_presupuesto[row["Categoría"]] = nuevo

        if hubo_cambio:
            save_budget_topes(user_id, topes_presupuesto)
            st.session_state.topes_presupuesto = topes_presupuesto

    with col_alertas:
        st.markdown("**Estado de Consumo por Rubro:**")

        if not df_mes_actual.empty:
            df_gasto_cat = gasto_por_categoria(df_mes_actual)
        else:
            df_gasto_cat = pd.DataFrame(columns=["Categoría", "Total ($)"])

        alertas_lista = []
        for categoria in categorias_validas:
            gasto_real = to_money(
                df_gasto_cat[df_gasto_cat["Categoría"] == categoria]["Total ($)"].sum()
            )
            tope = to_money(topes_presupuesto[categoria])
            porcentaje = (gasto_real / tope * 100) if tope > 0 else Decimal("0")

            alertas_lista.append(
                {
                    "Categoría": categoria,
                    "Consumido Real ($)": float(gasto_real),
                    "Límite Configurado ($)": float(tope),
                    "Porcentaje de Uso": f"{porcentaje:.1f}%",
                    "Excedido": gasto_real > tope,
                }
            )

        df_alertas_render = pd.DataFrame(alertas_lista)

        def estilizar_tabla_presupuesto(row):
            if row["Excedido"]:
                return [
                    "background-color: #ffcccc; color: #b71c1c; font-weight: bold;"
                ] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_alertas_render.style.apply(estilizar_tabla_presupuesto, axis=1),
            width="stretch",
            hide_index=True,
            column_config={
                "Consumido Real ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Límite Configurado ($)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
