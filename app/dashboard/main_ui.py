import os
import time
import uuid
import hashlib
import secrets
import streamlit as st
import pandas as pd
import pypdf
import io
import plotly.express as px
from decimal import Decimal
from datetime import datetime, timezone, date
from dotenv import load_dotenv
from app.ai.extractor import InvoiceExtractor
from app.ai.classifier import ExpenseClassifier
from app.database.session import get_session, Base, get_engine
from app.database.models import DBGasto, DBGastoItem
from sqlalchemy.orm import joinedload
from sqlalchemy import func

load_dotenv()

def get_secret(key: str, default=""):
    val = os.getenv(key)
    if val:
        return val
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return default

ADMIN_PEPPER = get_secret("ADMIN_PEPPER", "")

st.set_page_config(page_title="Analizador de Balances IA", layout="wide", page_icon="📊")
st.markdown("""
    <style>
    button[data-testid="stBaseButton-header"] {display: none !important;}
    </style>
    """, unsafe_allow_html=True)

MAX_INVOICES_PER_USER = 5

def _get_user_id() -> str:
    uid = st.query_params.get("uid")
    if uid:
        return uid
    uid = str(uuid.uuid4())[:8]
    st.query_params["uid"] = uid
    return uid

def _count_user_invoices(user_id: str) -> int:
    with get_session() as db:
        return db.query(func.count(DBGasto.id)).filter(DBGasto.user_id == user_id).scalar()

@st.cache_resource
def get_ai_tools():
    return InvoiceExtractor(
        vision_model=st.session_state.get("vision_model"),
        text_model=st.session_state.get("text_model"),
    ), ExpenseClassifier(
        model=st.session_state.get("classifier_model"),
    )

class ExpenseDashboard:
    def __init__(self):
        self.extractor, self.classifier = get_ai_tools()
        Base.metadata.create_all(bind=get_engine())
        self.user_id = _get_user_id()
        
        if "topes_presupuesto" not in st.session_state:
            st.session_state.topes_presupuesto = {cat: 1000.0 for cat in self.classifier.categorias_validas}

    def _check_admin_login(self) -> bool:
        admin_password = get_secret("ADMIN_PASSWORD", "")
        if not admin_password:
            st.session_state.admin_mode = True
            return True

        if "admin_login_attempts" not in st.session_state:
            st.session_state.admin_login_attempts = 0
            st.session_state.admin_lockout_until = 0.0

        now = time.time()
        if now < st.session_state.admin_lockout_until:
            wait = int(st.session_state.admin_lockout_until - now)
            st.sidebar.error(f"⏳ Demasiados intentos. Espera {wait}s.")
            return False

        with st.sidebar.expander("🔐 Modo Admin", expanded=True):
            pwd = st.text_input("Contraseña de admin", type="password", key="admin_login_pwd")
            clicked = st.button("Ingresar", key="admin_login_btn", type="primary", use_container_width=True)
            if clicked:
                pepper = ADMIN_PEPPER or "expense-analyzer-default-pepper"
                pwd_hash = hashlib.pbkdf2_hmac('sha256', pwd.encode(), pepper.encode(), 100000).hex()
                admin_hash = hashlib.pbkdf2_hmac('sha256', admin_password.encode(), pepper.encode(), 100000).hex()
                ok = secrets.compare_digest(pwd_hash, admin_hash)
                if ok:
                    st.session_state.admin_login_attempts = 0
                    st.session_state.admin_lockout_until = 0.0
                    st.session_state.admin_mode = True
                    st.rerun()
                else:
                    st.session_state.admin_login_attempts += 1
                    attempts = st.session_state.admin_login_attempts
                    if attempts >= 5:
                        delay = min(60 * (attempts - 4), 900)
                        st.session_state.admin_lockout_until = now + delay
                        st.error(f"🔒 Bloqueado por {delay}s por seguridad.")
                    else:
                        st.error(f"Contraseña incorrecta. {5 - attempts} intento(s) restante(s).")
        return False

    def _is_admin(self) -> bool:
        if st.session_state.get("admin_mode"):
            return True
        query_params = st.query_params
        if "admin" not in query_params or query_params["admin"] != "1":
            return False
        return self._check_admin_login()

    def render(self):
        is_admin = self._is_admin()
        st.title("Analizador Inteligente de Gastos y Balances")
        
        invoices_used = _count_user_invoices(self.user_id)
        remaining = MAX_INVOICES_PER_USER - invoices_used
        
        st.sidebar.header("📥 Cargar Comprobante")
        if is_admin:
            st.sidebar.caption("♾️ Sin límite de facturas (modo administrador).")
        else:
            st.sidebar.caption(f"⚠️ Límite: {remaining} factura(s) restante(s) para proteger la API de IA.")
        uploaded_file = st.sidebar.file_uploader(
            "Subir Factura Externa (PDF o Imagen)", type=["pdf", "png", "jpg", "jpeg"],
            disabled=not is_admin and remaining <= 0
        )
        
        if uploaded_file and st.sidebar.button("Procesar con IA", disabled=not is_admin and remaining <= 0):
            self._process_file(uploaded_file, invoices_used, is_admin)

        if is_admin:
            st.sidebar.markdown("---")
            st.sidebar.markdown(f"<small>👑 Modo administrador activo</small>", unsafe_allow_html=True)
            if st.sidebar.button("🚪 Cerrar sesión admin", key="admin_logout"):
                del st.session_state["admin_mode"]
                st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros de Balance")
        
        año_actual = datetime.now().year
        fecha_inicio = st.sidebar.date_input("Fecha Inicio", date(año_actual, 1, 1))
        fecha_fin = st.sidebar.date_input("Fecha Fin", date(año_actual, 12, 31))

        if is_admin:
            with st.sidebar.expander("⚙️ Admin: Modelos IA", expanded=False):
                st.caption("Solo visible para administradores")
                vision_model = st.text_input(
                    "Modelo de Visión",
                    value=st.session_state.get("vision_model", "qwen/qwen3.6-27b"),
                    key="admin_vision"
                )
                text_model = st.text_input(
                    "Modelo de Texto",
                    value=st.session_state.get("text_model", "llama-3.3-70b-versatile"),
                    key="admin_text"
                )
                classifier_model = st.text_input(
                    "Modelo de Clasificación",
                    value=st.session_state.get("classifier_model", "llama-3.3-70b-versatile"),
                    key="admin_classifier"
                )
                if st.button("Aplicar modelos", key="admin_apply", type="primary"):
                    st.session_state["vision_model"] = vision_model
                    st.session_state["text_model"] = text_model
                    st.session_state["classifier_model"] = classifier_model
                    st.cache_resource.clear()
                    st.success("Modelos actualizados. Recarga la página para aplicar cambios.")

        if "pending_gasto" in st.session_state:
            self._render_confirmation_step()
        else:
            self._render_stats(fecha_inicio, fecha_fin)
            st.markdown("---")
            self._render_budget_alerts()

    def _process_file(self, file, invoices_used, is_admin=False):
        if not is_admin and invoices_used >= MAX_INVOICES_PER_USER:
            st.error(f"Límite de {MAX_INVOICES_PER_USER} facturas alcanzado.")
            return
        with st.spinner("La IA está analizando los conceptos del documento..."):
            try:
                if file.type == "application/pdf":
                    reader = pypdf.PdfReader(file)
                    text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                    raw_data = self.extractor.extract_from_text(text) if text.strip() else self.extractor.extract_from_image(file.getvalue(), "image/jpeg")
                else:
                    raw_data = self.extractor.extract_from_image(file.getvalue(), file.type)

                descripciones = [it["descripcion"] for it in raw_data["items"]]
                categorias_ia = self.classifier.classify_batch(descripciones)

                items_procesados = []
                total_calculado = Decimal("0.00")
                
                for i, it in enumerate(raw_data["items"]):
                    subtotal = Decimal(str(it["cantidad"])) * Decimal(str(it["precio_unitario"]))
                    total_calculado += subtotal
                    
                    items_procesados.append({
                        "descripcion": it["descripcion"],
                        "cantidad": float(it["cantidad"]),
                        "precio_unitario": float(it["precio_unitario"]),
                        "total_linea": float(subtotal),
                        "categoria": categorias_ia[i] if i < len(categorias_ia) else "Otros"
                    })
                    
                st.session_state.pending_gasto = {
                    "proveedor": raw_data["proveedor"],
                    "fecha": raw_data.get("fecha"),
                    "items": items_procesados,
                    "total_ia": float(total_calculado)
                }
                st.rerun()
            except Exception as e:
                st.error(f"Error crítico de procesamiento: {e}")

    def _render_confirmation_step(self):
        st.warning("📋 **Verificación Requerida:** Revisa los datos del gasto extraídos por la IA.")
        data = st.session_state.pending_gasto
        
        col_prov, col_fecha = st.columns(2)
        proveedor_editado = col_prov.text_input("Proveedor", data["proveedor"])
        
        fecha_value = data.get("fecha")
        if fecha_value:
            try:
                fecha_default = datetime.strptime(fecha_value, "%Y-%m-%d").date()
            except ValueError:
                fecha_default = date.today()
        else:
            fecha_default = date.today()
        fecha_editada = col_fecha.date_input("Fecha de la factura", value=fecha_default)
        
        edited_df = st.data_editor(
            pd.DataFrame(data["items"]), 
            use_container_width=True, 
            column_config={
                "descripcion": st.column_config.TextColumn("Concepto/Descripción", required=True),
                "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0001, required=True),
                "precio_unitario": st.column_config.NumberColumn("Precio U.", min_value=0.00, required=True),
                "total_linea": st.column_config.NumberColumn("Total", disabled=True, format="$%.2f"),
                "categoria": st.column_config.SelectboxColumn("Categoría", options=self.classifier.categorias_validas)
            }
        )

        total_recalculado = sum(float(row["cantidad"]) * float(row["precio_unitario"]) for _, row in edited_df.iterrows())
        total_original = data["total_ia"]
        
        st.markdown("---")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total Detectado por IA", f"${total_original:,.2f}")
        col_m2.metric("Total de Tabla Actual", f"${total_recalculado:,.2f}", delta=f"{total_recalculado - total_original:,.2f}")
        st.markdown("---")

        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar y Guardar", type="primary"):
            self._final_save(proveedor_editado, edited_df, total_recalculado, fecha_editada)
        if col2.button("❌ Cancelar"): 
            del st.session_state.pending_gasto
            st.rerun()

    def _final_save(self, proveedor, df_final, total_recalculado, fecha):
        try:
            timestamp = int(datetime.now(timezone.utc).timestamp())
            fecha_dt = datetime.combine(fecha, datetime.min.time()).replace(tzinfo=timezone.utc) if fecha else datetime.now(timezone.utc)
            with get_session() as db:
                db_gasto = DBGasto(
                    user_id=self.user_id,
                    numero_comprobante=f"EXP-{timestamp}",
                    proveedor=proveedor,
                    fecha=fecha_dt,
                    total_gasto=float(total_recalculado)
                )
                db_gasto.items = [
                    DBGastoItem(
                        descripcion=str(row["descripcion"]),
                        cantidad=float(row["cantidad"]),
                        precio_unitario=float(row["precio_unitario"]),
                        total_linea=float(row["cantidad"]) * float(row["precio_unitario"]),
                        categoria=str(row["categoria"]),
                        gasto=db_gasto
                    ) for _, row in df_final.iterrows()
                ]
                db.add(db_gasto)
                db.commit()

            st.success("¡Gasto integrado al balance con éxito!")
            del st.session_state.pending_gasto
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    def _render_budget_alerts(self):
        st.subheader("🚨 Control de Presupuestos Mensuales")
        
        with get_session() as db:
            items_query = db.query(DBGastoItem).options(joinedload(DBGastoItem.gasto)).filter(
                DBGasto.user_id == self.user_id
            ).all()
            
        if not items_query:
            return

        mes_actual_str = datetime.now().strftime("%Y-%m")
        datos_completo = [
            {
                "Total ($)": float(it.total_linea),
                "Categoría": it.categoria,
                "Mes": it.gasto.fecha.strftime("%Y-%m")
            } for it in items_query
        ]
        df_all = pd.DataFrame(datos_completo)
        df_mes_actual = df_all[df_all["Mes"] == mes_actual_str]

        col_config, col_alertas = st.columns([1, 2])
        
        with col_config:
            st.markdown(f"**Ajustar topes mensuales ({mes_actual_str}):**")
            df_topes_input = pd.DataFrame([
                {"Categoría": cat, "Tope Mensual ($)": float(st.session_state.topes_presupuesto[cat])}
                for cat in self.classifier.categorias_validas
            ])
            
            edited_topes_df = st.data_editor(
                df_topes_input, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Categoría": st.column_config.TextColumn(
                        "Categoría", 
                        disabled=True
                    ),
                    "Tope Mensual ($)": st.column_config.NumberColumn(
                        "Tope Mensual ($)", 
                        min_value=0.0, 
                        format="$%.2f",
                        step=10.0
                    )
                }
            )
            
            for _, row in edited_topes_df.iterrows():
                st.session_state.topes_presupuesto[row["Categoría"]] = float(row["Tope Mensual ($)"])

        with col_alertas:
            st.markdown("**Estado de Consumo por Rubro:**")
            
            if not df_mes_actual.empty:
                df_gasto_cat = df_mes_actual.groupby("Categoría")["Total ($)"].sum().reset_index()
            else:
                df_gasto_cat = pd.DataFrame(columns=["Categoría", "Total ($)"])

            alertas_lista = []
            for cat in self.classifier.categorias_validas:
                gasto_real = float(df_gasto_cat[df_gasto_cat["Categoría"] == cat]["Total ($)"].sum())
                tope = float(st.session_state.topes_presupuesto[cat])
                porcentaje = (gasto_real / tope * 100) if tope > 0 else 0
                
                alertas_lista.append({
                    "Categoría": cat,
                    "Consumido Real ($)": gasto_real,
                    "Límite Configurado ($)": tope,
                    "Porcentaje de Uso": f"{porcentaje:.1f}%",
                    "Excedido": gasto_real > tope
                })
            
            df_alertas_render = pd.DataFrame(alertas_lista)
            
            def estilizar_tabla_presupuesto(row):
                if row["Excedido"]:
                    return ['background-color: #ffcccc; color: #b71c1c; font-weight: bold;'] * len(row)
                return [''] * len(row)

            df_mostrar = df_alertas_render.drop(columns=["Excedido"])

            st.dataframe(
                df_alertas_render.style.apply(estilizar_tabla_presupuesto, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Consumido Real ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Límite Configurado ($)": st.column_config.NumberColumn(format="$%.2f")
                }
            )

    def _render_stats(self, start_date, end_date):
        with get_session() as db:
            items_query = db.query(DBGastoItem).options(joinedload(DBGastoItem.gasto)).filter(
                DBGasto.user_id == self.user_id
            ).all()
            gastos_cabecera = db.query(DBGasto).filter(DBGasto.user_id == self.user_id).all()
            
            if not items_query:
                st.info("Sin registros de gastos cargados en el sistema.")
                return

            datos_tabla = [
                {
                    "ID Comprobante": it.gasto.numero_comprobante,
                    "Proveedor": it.gasto.proveedor,
                    "Fecha": it.gasto.fecha.strftime("%Y-%m-%d"),
                    "Concepto": it.descripcion,
                    "Cantidad": float(it.cantidad),
                    "Precio U. ($)": float(it.precio_unitario),
                    "Total ($)": float(it.total_linea),
                    "Categoría": it.categoria
                } for it in items_query
            ]
            
            datos_cabecera_lista = [
                {
                    "id_db": g.id,
                    "Comprobante": g.numero_comprobante,
                    "Proveedor": g.proveedor,
                    "Fecha": g.fecha.strftime("%Y-%m-%d %H:%M"),
                    "Total Gasto ($)": float(g.total_gasto)
                } for g in gastos_cabecera
            ]
            
        df_completo = pd.DataFrame(datos_tabla)
        df_completo["Fecha_DT"] = pd.to_datetime(df_completo["Fecha"]).dt.date
        df_base = df_completo[(df_completo["Fecha_DT"] >= start_date) & (df_completo["Fecha_DT"] <= end_date)].copy()
        
        if df_base.empty:
            st.warning(f"No existen transacciones registradas en el rango desde {start_date} hasta {end_date}.")
            return

        df_agrupado = df_base.groupby(["Concepto", "Categoría", "Proveedor"]).agg(
            Repeticiones=("Total ($)", "count"),
            Cantidad_Acumulada=("Cantidad", "sum"),
            Monto_Total_Gastado=("Total ($)", "sum")
        ).reset_index().sort_values(by="Monto_Total_Gastado", ascending=False)

        col1, col2, col3 = st.columns(3)
        col1.metric("Gasto Filtrado Acumulado", f"${df_base['Total ($)'].sum():,.2f}")
        col2.metric("Conceptos Distintos en Rango", len(df_agrupado))
        col3.metric("Proveedores en Rango", df_base["Proveedor"].nunique())
        
        st.markdown("---")
        st.markdown("### 📈 Evolución Temporal de Salidas")
        df_base["Mes_Periodo"] = pd.to_datetime(df_base["Fecha"]).dt.to_period("M").astype(str)
        df_mensual = df_base.groupby("Mes_Periodo")["Total ($)"].sum().reset_index().sort_values(by="Mes_Periodo")
        
        fig_linea = px.line(
            df_mensual, x="Mes_Periodo", y="Total ($)", markers=True,
            labels={"Mes_Periodo": "Mes de Operación", "Total ($)": "Egresos Consolidados ($)"}
        )
        fig_linea.update_layout(hovermode="x unified", template="plotly_white")
        fig_linea.update_traces(line_color="#c0392b", line_width=3, marker=dict(size=8))
        st.plotly_chart(fig_linea, use_container_width=True)
        
        st.markdown("---")
        df_exportar = df_base.drop(columns=["Fecha_DT", "Mes_Periodo"])
        
        is_admin = st.session_state.get("admin_mode", False)
        tabs_list = [
            "📊 Conceptos Consolidados (Agrupados)",
            "📋 Historial Filtrado",
            "📐 Participación de Rubros",
        ]
        if is_admin:
            tabs_list.append("🔥 Administrar y Purgar")
        tabs = st.tabs(tabs_list)
        tab1, tab2, tab3 = tabs[0], tabs[1], tabs[2]
        tab4 = tabs[3] if is_admin else None
        
        with tab1:
            st.markdown(f"### 🔄 Gastos Agrupados Automáticamente ({start_date} a {end_date})")
            st.dataframe(df_agrupado, use_container_width=True, hide_index=True)
            
        with tab2:
            col_header, col_download = st.columns([4, 1])
            col_header.markdown("### 📜 Transacciones Extraídas en el Periodo")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exportar.to_excel(writer, index=False, sheet_name='Historial Filtrado')
                df_agrupado.to_excel(writer, index=False, sheet_name='Balance Consolidado')
            
            col_download.download_button(
                label="📥 Descargar Reporte en Excel",
                data=buffer.getvalue(),
                file_name=f"balance_gastos_ia_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.dataframe(df_exportar, use_container_width=True, hide_index=True)

        with tab3:
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.write("**Gastos por Categoría Financiera:**")
                df_cat = df_base.groupby("Categoría")["Total ($)"].sum().reset_index()
                fig_bar = px.bar(df_cat, x="Categoría", y="Total ($)", text_auto='.2f', color="Categoría", color_discrete_sequence=px.colors.qualitative.Safe)
                fig_bar.update_layout(showlegend=False, template="plotly_white")
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_g2:
                st.write("**Participación por Proveedor:**")
                df_prov = df_base.groupby("Proveedor")["Total ($)"].sum().reset_index()
                fig_pie = px.pie(df_prov, values="Total ($)", names="Proveedor", color_discrete_sequence=px.colors.qualitative.Safe)
                fig_pie.update_traces(textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)

        if tab4:
            with tab4:
                st.markdown("### 🗑️ Eliminación de Comprobantes Erróneos")
                st.write("Selecciona una factura de la lista desplegable para borrarla por completo del balance.")
                
                if datos_cabecera_lista:
                    df_cabecera = pd.DataFrame(datos_cabecera_lista)
                    
                    opciones_selectbox = {
                        row["id_db"]: f"{row['Comprobante']} | {row['Proveedor']} | ${row['Total Gasto ($)']:,.2f} ({row['Fecha']})"
                        for _, row in df_cabecera.iterrows()
                    }
                    
                    id_seleccionado = st.selectbox(
                        "Selecciona el registro a eliminar:", 
                        options=list(opciones_selectbox.keys()), 
                        format_func=lambda x: opciones_selectbox[x]
                    )
                    
                    st.error("⚠️ **Acción Irreversible:** Al hacer clic en borrar, se eliminará la cabecera y todas sus líneas de concepto asociadas.")
                    
                    if st.button("🔥 Confirmar Eliminación Definitiva", use_container_width=True):
                        try:
                            with get_session() as db:
                                registro_a_borrar = db.query(DBGasto).filter(
                                    DBGasto.id == id_seleccionado,
                                    DBGasto.user_id == self.user_id
                                ).first()
                                if registro_a_borrar:
                                    db.delete(registro_a_borrar)
                                    db.commit()
                                    st.success("Registro eliminado correctamente de la base de datos.")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar el registro: {e}")
                else:
                    st.info("No hay facturas registradas disponibles para purgar.")

if __name__ == "__main__":
    app = ExpenseDashboard()
    app.render()
