import os
import uuid
import streamlit as st
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from streamlit.errors import StreamlitAPIException
from sqlalchemy import func

from expense_analyzer.ai.extractor import InvoiceExtractor
from expense_analyzer.ai.classifier import ExpenseClassifier
from expense_analyzer.database.session import (
    get_fallback_reason,
    get_session,
    initialize_database,
)
from expense_analyzer.database.models import (
    CATEGORIA_POR_DEFECTO,
    DBGasto,
    DBGastoItem,
    DBPresupuestoTope,
    utc_now,
)
from expense_analyzer.money import invoice_total, line_total, to_money

load_dotenv()

TOPE_MENSUAL_POR_DEFECTO = 1000.0


def get_secret(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val:
        return val
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, StreamlitAPIException):
        return default


def get_admin_pepper() -> str:
    return get_secret("ADMIN_PEPPER", "") or "expense-analyzer-default-pepper"


def get_max_invoices_per_user() -> int:
    return int(get_secret("MAX_INVOICES_PER_USER", "5"))


def get_storage_warning() -> str:
    return get_fallback_reason() or ""


def get_user_id() -> str:
    uid = st.query_params.get("uid")
    if uid:
        return uid
    uid = uuid.uuid4().hex[:12]
    st.query_params["uid"] = uid
    return uid


def count_user_invoices(user_id: str, include_demo: bool = False) -> int:
    with get_session() as db:
        query = db.query(func.count(DBGasto.id)).filter(DBGasto.user_id == user_id)
        if not include_demo:
            query = query.filter(DBGasto.es_demo.is_(False))
        return query.scalar()


def get_ai_models() -> tuple[str, str, str]:
    return (
        st.session_state.get("vision_model") or None,
        st.session_state.get("text_model") or None,
        st.session_state.get("classifier_model") or None,
    )


@st.cache_resource(show_spinner=False)
def _build_ai_tools(vision_model, text_model, classifier_model):
    return (
        InvoiceExtractor(vision_model=vision_model, text_model=text_model),
        ExpenseClassifier(model=classifier_model),
    )


def get_ai_tools():
    return _build_ai_tools(*get_ai_models())


def generar_numero_comprobante(prefijo: str = "EXP") -> str:
    ahora = utc_now()
    sufijo = uuid.uuid4().hex[:6].upper()
    return f"{prefijo}-{ahora:%Y%m%d}-{sufijo}"


DEMO_INVOICE_SOURCES = [
    {
        "proveedor": "Amazon Web Services",
        "dias_atras": 4,
        "items": [
            {
                "descripcion": "Instancia EC2 t3.large (produccion)",
                "cantidad": 2,
                "precio_unitario": 245.50,
                "categoria": "Infraestructura Cloud & Hosting",
            },
            {
                "descripcion": "Almacenamiento S3 Standard - 2 TB",
                "cantidad": 1,
                "precio_unitario": 89.99,
                "categoria": "Infraestructura Cloud & Hosting",
            },
            {
                "descripcion": "Base de datos RDS MySQL (clase db.t4g.medium)",
                "cantidad": 1,
                "precio_unitario": 178.25,
                "categoria": "Infraestructura Cloud & Hosting",
            },
        ],
    },
    {
        "proveedor": "Slack Technologies",
        "dias_atras": 12,
        "items": [
            {
                "descripcion": "Suscripcion Slack Pro - 15 usuarios",
                "cantidad": 15,
                "precio_unitario": 12.50,
                "categoria": "Herramientas SaaS & Software",
            },
            {
                "descripcion": "Slack Connect - integraciones externas",
                "cantidad": 1,
                "precio_unitario": 64.00,
                "categoria": "Herramientas SaaS & Software",
            },
        ],
    },
    {
        "proveedor": "Meta Ads",
        "dias_atras": 21,
        "items": [
            {
                "descripcion": "Campana Instagram Q2 - Lead Generation",
                "cantidad": 1,
                "precio_unitario": 1500.00,
                "categoria": "Marketing, Publicidad & SEO",
            },
            {
                "descripcion": "Campana Facebook Retargeting",
                "cantidad": 1,
                "precio_unitario": 850.00,
                "categoria": "Marketing, Publicidad & SEO",
            },
        ],
    },
    {
        "proveedor": "Dell Technologies",
        "dias_atras": 38,
        "items": [
            {
                "descripcion": "Laptop Dell Latitude 5540 para equipo comercial",
                "cantidad": 3,
                "precio_unitario": 1250.00,
                "categoria": "Hardware & Equipamiento de Oficina",
            },
            {
                "descripcion": 'Monitor Dell UltraSharp 27"',
                "cantidad": 3,
                "precio_unitario": 450.00,
                "categoria": "Hardware & Equipamiento de Oficina",
            },
        ],
    },
    {
        "proveedor": "Agencia Norte Consulting",
        "dias_atras": 55,
        "items": [
            {
                "descripcion": "Consultoria de arquitectura de datos (40 h)",
                "cantidad": 40,
                "precio_unitario": 55.00,
                "categoria": "Servicios Profesionales & Outsourcing",
            },
        ],
    },
    {
        "proveedor": "Airline Andina del Norte",
        "dias_atras": 78,
        "items": [
            {
                "descripcion": "Vuelos Bogota - Madrid (2 pasajeros)",
                "cantidad": 2,
                "precio_unitario": 620.00,
                "categoria": "Viajes, Viáticos & Transporte",
            },
            {
                "descripcion": "Hotel - 4 noches de Hospedaje",
                "cantidad": 4,
                "precio_unitario": 180.00,
                "categoria": "Viajes, Viáticos & Transporte",
            },
        ],
    },
    {
        "proveedor": "Universidad Tecnica del Norte",
        "dias_atras": 104,
        "items": [
            {
                "descripcion": "Curso avanzado de machine learning (cohorte)",
                "cantidad": 6,
                "precio_unitario": 220.00,
                "categoria": "Suscripciones & Educación",
            },
        ],
    },
]

DEMO_TOPES = {
    "Infraestructura Cloud & Hosting": 900.0,
    "Herramientas SaaS & Software": 700.0,
    "Servicios Profesionales & Outsourcing": 1500.0,
    "Marketing, Publicidad & SEO": 3000.0,
    "Hardware & Equipamiento de Oficina": 5000.0,
    "Suscripciones & Educación": 800.0,
    "Viajes, Viáticos & Transporte": 1500.0,
    "Gastos Operativos Generales": 400.0,
    "Otros": 300.0,
}


def clear_user_data(user_id: str) -> None:
    with get_session() as db:
        db.query(DBPresupuestoTope).filter(DBPresupuestoTope.user_id == user_id).delete()
        gastos = db.query(DBGasto).filter(DBGasto.user_id == user_id).all()
        for gasto in gastos:
            db.delete(gasto)
        db.commit()


def seed_demo_data(user_id: str) -> int:
    clear_user_data(user_id)
    ahora = utc_now()
    count = 0
    with get_session() as db:
        for invoice in DEMO_INVOICE_SOURCES:
            fecha = ahora - timedelta(days=invoice["dias_atras"])
            total_gasto = invoice_total(invoice["items"])
            db_gasto = DBGasto(
                user_id=user_id,
                numero_comprobante=generar_numero_comprobante("DEMO"),
                proveedor=invoice["proveedor"],
                fecha=fecha,
                total_gasto=total_gasto,
                es_demo=True,
            )
            db_gasto.items = [
                DBGastoItem(
                    descripcion=item["descripcion"],
                    cantidad=item["cantidad"],
                    precio_unitario=item["precio_unitario"],
                    total_linea=line_total(item["cantidad"], item["precio_unitario"]),
                    categoria=item["categoria"],
                )
                for item in invoice["items"]
            ]
            db.add(db_gasto)
            count += 1
        db.commit()
    save_budget_topes(user_id, dict(DEMO_TOPES))
    return count


def load_budget_topes(user_id: str, categorias_validas: list[str]) -> dict:
    topes = {}
    with get_session() as db:
        rows = (
            db.query(DBPresupuestoTope)
            .filter(DBPresupuestoTope.user_id == user_id)
            .all()
        )
        for row in rows:
            topes[row.categoria] = float(row.tope_mensual)
    for cat in categorias_validas:
        topes.setdefault(cat, TOPE_MENSUAL_POR_DEFECTO)
    return topes


def save_budget_topes(user_id: str, topes: dict) -> None:
    with get_session() as db:
        db.query(DBPresupuestoTope).filter(DBPresupuestoTope.user_id == user_id).delete()
        for categoria, tope in topes.items():
            db.add(
                DBPresupuestoTope(
                    user_id=user_id,
                    categoria=categoria,
                    tope_mensual=to_money(tope),
                )
            )
        db.commit()


def build_pending_payload(raw_data: dict, categorias_ia: list[str]) -> dict:
    items_procesados = []
    for i, item in enumerate(raw_data["items"]):
        cantidad = item["cantidad"]
        precio_unitario = item["precio_unitario"]
        items_procesados.append(
            {
                "descripcion": item["descripcion"],
                "cantidad": float(cantidad),
                "precio_unitario": float(precio_unitario),
                "total_linea": float(line_total(cantidad, precio_unitario)),
                "categoria": categorias_ia[i]
                if i < len(categorias_ia)
                else CATEGORIA_POR_DEFECTO,
            }
        )
    return {
        "proveedor": raw_data["proveedor"],
        "fecha": raw_data.get("fecha"),
        "items": items_procesados,
        "total_ia": float(invoice_total(raw_data["items"])),
    }


def save_approved_invoice(
    user_id: str,
    proveedor: str,
    fecha: date | None,
    items_finales: list[dict],
    total_recalculado,
    file_hash: str = None,
) -> str:
    if not items_finales:
        raise ValueError("No se puede guardar una factura sin items.")

    fecha_dt = (
        datetime.combine(fecha, datetime.min.time())
        if isinstance(fecha, date)
        else utc_now()
    )
    total_gasto = to_money(total_recalculado)
    if not total_gasto:
        total_gasto = invoice_total(items_finales)

    with get_session() as db:
        numero = generar_numero_comprobante()
        db_gasto = DBGasto(
            user_id=user_id,
            numero_comprobante=numero,
            proveedor=proveedor,
            fecha=fecha_dt,
            total_gasto=total_gasto,
            file_hash=file_hash,
            es_demo=False,
        )
        db_gasto.items = [
            DBGastoItem(
                descripcion=str(item["descripcion"]),
                cantidad=item["cantidad"],
                precio_unitario=item["precio_unitario"],
                total_linea=line_total(item["cantidad"], item["precio_unitario"]),
                categoria=str(item.get("categoria") or CATEGORIA_POR_DEFECTO),
            )
            for item in items_finales
        ]
        db.add(db_gasto)
        db.commit()
    return numero


def delete_gasto(user_id: str, gasto_id: int) -> bool:
    with get_session() as db:
        gasto = (
            db.query(DBGasto)
            .filter(DBGasto.id == gasto_id, DBGasto.user_id == user_id)
            .first()
        )
        if not gasto:
            return False
        db.delete(gasto)
        db.commit()
        return True
