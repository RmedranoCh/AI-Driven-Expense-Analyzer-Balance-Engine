import time
import hashlib
import secrets as _secrets
import streamlit as st
import pandas as pd
import pypdf
from datetime import datetime, timezone, date

from expense_analyzer.dashboard import services
from expense_analyzer.dashboard import views
from expense_analyzer.dashboard import styles
from expense_analyzer.dashboard.services import (
    get_secret,
    get_admin_pepper,
    get_max_invoices_per_user,
    initialize_database,
    get_user_id,
    count_user_invoices,
    get_ai_tools,
    seed_demo_data,
    build_pending_payload,
    save_approved_invoice,
)


class ExpenseDashboard:
    def __init__(self):
        self.extractor, self.classifier = get_ai_tools()
        initialize_database()
        self.user_id = get_user_id()

        if "processed_hashes" not in st.session_state:
            st.session_state.processed_hashes = set()
        if "processing" not in st.session_state:
            st.session_state.processing = False

        st.session_state.topes_presupuesto = services.load_budget_topes(
            self.user_id, self.classifier.categorias_validas
        )

    def render(self):
        is_admin = self._is_admin()
        st.title("Analizador Inteligente de Gastos y Balances")

        invoices_used = count_user_invoices(self.user_id)
        if invoices_used == 0:
            seed_demo_data(self.user_id)
            invoices_used = count_user_invoices(self.user_id)
            st.rerun()

        max_invoices = get_max_invoices_per_user()
        remaining = max_invoices - invoices_used

        st.sidebar.header("📥 Cargar Comprobante")
        if is_admin:
            st.sidebar.caption("♾️ Sin límite de facturas (modo administrador).")
        else:
            st.sidebar.caption(
                f"⚠️ Límite: {remaining} factura(s) restante(s) para proteger la API de IA."
            )

        processing = st.session_state.get("processing", False)

        uploaded_file = st.sidebar.file_uploader(
            "Subir Factura Externa (PDF o Imagen)",
            type=["pdf", "png", "jpg", "jpeg"],
            disabled=(not is_admin and remaining <= 0) or processing,
            key="file_uploader",
        )

        btn_disabled = (
            (not is_admin and remaining <= 0) or processing or uploaded_file is None
        )
        if st.sidebar.button("Procesar con IA", disabled=btn_disabled, key="process_btn"):
            st.session_state.processing = True
            st.session_state.file_to_process = uploaded_file
            st.rerun()

        if st.session_state.get("processing") and st.session_state.get("file_to_process"):
            self._process_file(st.session_state.file_to_process, is_admin)
            st.session_state.processing = False
            st.session_state.file_to_process = None
            st.rerun()

        with st.sidebar.expander("🔁 Restablecer datos demo", expanded=False):
            st.caption("Limpia todos los datos y carga ejemplos predefinidos.")
            if st.button("📦 Cargar datos demo", use_container_width=True):
                seed_demo_data(self.user_id)
                st.session_state.processed_hashes = set()
                st.rerun()

        if is_admin:
            st.sidebar.markdown("---")
            st.sidebar.markdown(
                f"<small>👑 Modo administrador activo</small>", unsafe_allow_html=True
            )
            if st.sidebar.button("🚪 Cerrar sesión admin", key="admin_logout"):
                del st.session_state["admin_mode"]
                st.rerun()

        with st.sidebar.expander("🔒 Privacidad", expanded=False):
            st.caption("""
            **¿Qué pasa con tus datos?**  
            - Los comprobantes que subes se envían a **Groq AI** para extraer y clasificar la información.  
            - Los datos extraídos se guardan temporalmente en la base de datos local.  
            - **No compartimos ni almacenamos tus facturas fuera de esta sesión.**  
            - Puedes limpiar todos tus datos en cualquier momento con "Restablecer datos demo".  
            - Este es un proyecto de demostración; no uses datos sensibles o confidenciales.
            """)

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
                    key="admin_vision",
                )
                text_model = st.text_input(
                    "Modelo de Texto",
                    value=st.session_state.get("text_model", "openai/gpt-oss-120b"),
                    key="admin_text",
                )
                classifier_model = st.text_input(
                    "Modelo de Clasificación",
                    value=st.session_state.get("classifier_model", "openai/gpt-oss-120b"),
                    key="admin_classifier",
                )
                if st.button("Aplicar modelos", key="admin_apply", type="primary"):
                    st.session_state["vision_model"] = vision_model
                    st.session_state["text_model"] = text_model
                    st.session_state["classifier_model"] = classifier_model
                    st.cache_resource.clear()
                    st.success("Modelos actualizados. Recarga la página para aplicar cambios.")

        if st.session_state.get("processing"):
            st.markdown(
                """
                <div style="text-align: center; padding: 20px 0;">
                    <p style="font-size: 1.2rem; color: #555;">
                        Analizando documento con IA
                    </p>
                    <div class="processing-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if "pending_gasto" in st.session_state:
            self._render_confirmation_step()
        else:
            views.render_dashboard_stats(self.user_id, fecha_inicio, fecha_fin)
            st.markdown("---")
            views.render_budget_alerts(self.user_id, self.classifier.categorias_validas)

    def _process_file(self, file, is_admin=False):
        invoices_used = count_user_invoices(self.user_id)
        max_invoices = get_max_invoices_per_user()
        if not is_admin and invoices_used >= max_invoices:
            st.error(f"Límite de {max_invoices} facturas alcanzado.")
            return

        file_bytes = file.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        if file_hash in st.session_state.processed_hashes:
            st.warning(
                "⚠️ Esta factura ya fue analizada en esta sesión. "
                "Si es el mismo archivo, recarga la página e inténtalo de nuevo."
            )
            return
        st.session_state.processed_hashes.add(file_hash)

        from expense_analyzer.database.session import get_session
        from expense_analyzer.database.models import DBGasto

        with get_session() as db:
            existente = (
                db.query(DBGasto)
                .filter(DBGasto.user_id == self.user_id, DBGasto.file_hash == file_hash)
                .first()
            )
            if existente:
                st.warning(
                    f"⚠️ Esta factura ya fue registrada anteriormente como '{existente.proveedor}'."
                )
                return

        status = st.status("Iniciando análisis del documento...", expanded=True)
        try:
            status.update(label="📄 Leyendo contenido del archivo...")
            if file.type == "application/pdf":
                reader = pypdf.PdfReader(file)
                text = "\n".join(
                    [page.extract_text() for page in reader.pages if page.extract_text()]
                )
                if text.strip():
                    status.update(label="🤖 Enviando texto a IA para extraer datos...")
                    raw_data = self.extractor.extract_from_text(text)
                else:
                    status.update(label="🖼️ Procesando imagen del PDF con IA de visión...")
                    raw_data = self.extractor.extract_from_image(file.getvalue(), "image/jpeg")
            else:
                status.update(label="🖼️ Analizando imagen con IA de visión...")
                raw_data = self.extractor.extract_from_image(file.getvalue(), file.type)

            status.update(label="🏷️ Clasificando conceptos con IA...")
            descripciones = [item["descripcion"] for item in raw_data["items"]]
            categorias_ia = self.classifier.classify_batch(descripciones)

            status.update(label="📊 Preparando datos para revisión...")
            pending = build_pending_payload(raw_data, categorias_ia)
            pending["_file_hash"] = file_hash
            st.session_state.pending_gasto = pending
            status.update(label="✅ Análisis completado con éxito", state="complete")
            st.rerun()
        except Exception as e:
            status.update(label="❌ Error en el procesamiento", state="error")
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
                "categoria": st.column_config.SelectboxColumn(
                    "Categoría", options=self.classifier.categorias_validas
                ),
            },
        )

        total_recalculado = sum(
            float(row["cantidad"]) * float(row["precio_unitario"])
            for _, row in edited_df.iterrows()
        )
        total_original = data["total_ia"]

        st.markdown("---")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total Detectado por IA", f"${total_original:,.2f}")
        col_m2.metric(
            "Total de Tabla Actual",
            f"${total_recalculado:,.2f}",
            delta=f"{total_recalculado - total_original:,.2f}",
        )
        st.markdown("---")

        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar y Guardar", type="primary"):
            self._final_save(proveedor_editado, edited_df, total_recalculado, fecha_editada)
        if col2.button("❌ Cancelar"):
            file_name_hash = data.get("_file_hash")
            if file_name_hash and file_name_hash in st.session_state.processed_hashes:
                st.session_state.processed_hashes.discard(file_name_hash)
            del st.session_state.pending_gasto
            st.rerun()

    def _final_save(self, proveedor, df_final, total_recalculado, fecha):
        try:
            file_hash = st.session_state.pending_gasto.get("_file_hash")
            items_finales = [
                {
                    "descripcion": str(row["descripcion"]),
                    "cantidad": str(row["cantidad"]),
                    "precio_unitario": str(row["precio_unitario"]),
                    "categoria": str(row["categoria"]),
                }
                for _, row in df_final.iterrows()
            ]
            save_approved_invoice(
                user_id=self.user_id,
                proveedor=proveedor,
                fecha=fecha,
                items_finales=items_finales,
                total_recalculado=total_recalculado,
                file_hash=file_hash,
            )
            st.success("¡Gasto integrado al balance con éxito!")
            del st.session_state.pending_gasto
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

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
                pepper = get_admin_pepper()
                pwd_hash = hashlib.pbkdf2_hmac('sha256', pwd.encode(), pepper.encode(), 100000).hex()
                admin_hash = hashlib.pbkdf2_hmac('sha256', admin_password.encode(), pepper.encode(), 100000).hex()
                ok = _secrets.compare_digest(pwd_hash, admin_hash)
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


if __name__ == "__main__":
    styles.configure_page()
    app = ExpenseDashboard()
    app.render()