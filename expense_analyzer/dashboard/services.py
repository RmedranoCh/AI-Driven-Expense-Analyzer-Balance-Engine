import os
import uuid
import streamlit as st
from decimal import Decimal
from datetime import datetime, timezone, date, timedelta
from dotenv import load_dotenv
from sqlalchemy import func

from expense_analyzer.ai.extractor import InvoiceExtractor
from expense_analyzer.ai.classifier import ExpenseClassifier
from expense_analyzer.database.session import get_session, Base, get_engine
from expense_analyzer.database.models import DBGasto, DBGastoItem, DBPresupuestoTope

load_dotenv()


def get_secret(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val:
        return val
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return default


def get_admin_pepper() -> str:
    return get_secret("ADMIN_PEPPER", "") or "expense-analyzer-default-pepper"


def get_max_invoices_per_user() -> int:
    return int(get_secret("MAX_INVOICES_PER_USER", "5"))


def initialize_database() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_user_id() -> str:
    uid = st.query_params.get("uid")
    if uid:
        return uid
    uid = str(uuid.uuid4())[:8]
    st.query_params["uid"] = uid
    return uid


def count_user_invoices(user_id: str) -> int:
    with get_session() as db:
        return db.query(func.count(DBGasto.id)).filter(DBGasto.user_id == user_id).scalar()


@st.cache_resource
def get_ai_tools():
    return (
        InvoiceExtractor(
            vision_model=st.session_state.get("vision_model"),
            text_model=st.session_state.get("text_model"),
        ),
        ExpenseClassifier(
            model=st.session_state.get("classifier_model"),
        ),
    )


DEMO_INVOICE_SOURCES = [
    {
        "proveedor": "Amazon Web Services",
        "dias_atras": 40,
        "items": [
            {"descripcion": "Servicio EC2 - Instancia t3.large", "cantidad": 1, "precio_unitario": 245.50, "categoria": "Infraestructura Cloud & Hosting"},
            {"descripcion": "Almacenamiento S3 Standard", "cantidad": 1, "precio_unitario": 89.99, "categoria": "Infraestructura Cloud & Hosting"},
            {"descripcion": "Base de Datos RDS - MySQL", "cantidad": 1, "precio_unitario": 178.25, "categoria": "Infraestructura Cloud & Hosting"},
        ],
    },
    {
        "proveedor": "Slack Technologies",
        "dias_atras": 45,
        "items": [
            {"descripcion": "Suscripción Slack Pro - 15 usuarios", "cantidad": 15, "precio_unitario": 12.50, "categoria": "Herramientas SaaS & Software"},
        ],
    },
    {
        "proveedor": "Meta Ads",
        "dias_atras": 30,
        "items": [
            {"descripcion": "Campaña Instagram Q2 - Lead Generation", "cantidad": 1, "precio_unitario": 1500.00, "categoria": "Marketing, Publicidad & SEO"},
            {"descripcion": "Campaña Facebook Retargeting", "cantidad": 1, "precio_unitario": 850.00, "categoria": "Marketing, Publicidad & SEO"},
        ],
    },
    {
        "proveedor": "Dell Technologies",
        "dias_atras": 55,
        "items": [
            {"descripcion": "Laptop Dell Latitude 5540", "cantidad": 3, "precio_unitario": 1250.00, "categoria": "Hardware & Equipamiento de Oficina"},
            {"descripcion": "Monitor Dell UltraSharp 27\"", "cantidad": 3, "precio_unitario": 450.00, "categoria": "Hardware & Equipamiento de Oficina"},
        ],
    },
]


def clear_user_data(user_id: str) -> None:
    with get_session() as db:
        db.query(DBPresupuestoTope).filter(DBPresupuestoTope.user_id == user_id).delete()
        gastos = db.query(DBGasto).filter(DBGasto.user_id == user_id).all()
        for gasto in gastos:
            db.delete(gasto)
        db.commit()


def seed_demo_data(user_id: str) -> int:
    clear_user_data(user_id)
    count = 0
    with get_session() as db:
        for invoice in DEMO_INVOICE_SOURCES:
            fecha = datetime.now(timezone.utc) - timedelta(days=invoice["dias_atras"])
            db_items = [
                DBGastoItem(
                    descripcion=item["descripcion"],
                    cantidad=Decimal(str(item["cantidad"])),
                    precio_unitario=Decimal(str(item["precio_unitario"])),
                    total_linea=Decimal(str(item["cantidad"]))
                    * Decimal(str(item["precio_unitario"])),
                    categoria=item["categoria"],
                )
                for item in invoice["items"]
            ]
            total_gasto = sum(
                Decimal(str(item["cantidad"])) * Decimal(str(item["precio_unitario"]))
                for item in invoice["items"]
            )
            db_gasto = DBGasto(
                user_id=user_id,
                numero_comprobante=f"DEMO-{int(fecha.timestamp())}",
                proveedor=invoice["proveedor"],
                fecha=fecha,
                total_gasto=total_gasto,
            )
            db_gasto.items = db_items
            db.add(db_gasto)
            count += 1
        db.commit()
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
        topes.setdefault(cat, 1000.0)
    return topes


def save_budget_topes(user_id: str, topes: dict) -> None:
    with get_session() as db:
        db.query(DBPresupuestoTope).filter(DBPresupuestoTope.user_id == user_id).delete()
        for categoria, tope in topes.items():
            db.add(
                DBPresupuestoTope(
                    user_id=user_id,
                    categoria=categoria,
                    tope_mensual=float(tope),
                )
            )
        db.commit()


def build_pending_payload(raw_data: dict, categorias_ia: list[str]) -> dict:
    items_procesados = []
    total_calculado = Decimal("0.00")
    for i, item in enumerate(raw_data["items"]):
        subtotal = Decimal(str(item["cantidad"])) * Decimal(str(item["precio_unitario"]))
        total_calculado += subtotal
        items_procesados.append(
            {
                "descripcion": item["descripcion"],
                "cantidad": float(item["cantidad"]),
                "precio_unitario": float(item["precio_unitario"]),
                "total_linea": float(subtotal),
                "categoria": categorias_ia[i] if i < len(categorias_ia) else "Otros",
            }
        )
    return {
        "proveedor": raw_data["proveedor"],
        "fecha": raw_data.get("fecha"),
        "items": items_procesados,
        "total_ia": float(total_calculado),
    }


def save_approved_invoice(
    user_id: str,
    proveedor: str,
    fecha: date,
    items_finales: list[dict],
    total_recalculado: float,
    file_hash: str = None,
) -> None:
    timestamp = int(datetime.now(timezone.utc).timestamp())
    fecha_dt = (
        datetime.combine(fecha, datetime.min.time()).replace(tzinfo=timezone.utc)
        if fecha
        else datetime.now(timezone.utc)
    )
    with get_session() as db:
        db_gasto = DBGasto(
            user_id=user_id,
            numero_comprobante=f"EXP-{timestamp}",
            proveedor=proveedor,
            fecha=fecha_dt,
            total_gasto=Decimal(str(total_recalculado)),
            file_hash=file_hash,
        )
        db_gasto.items = [
            DBGastoItem(
                descripcion=str(item["descripcion"]),
                cantidad=Decimal(str(item["cantidad"])),
                precio_unitario=Decimal(str(item["precio_unitario"])),
                total_linea=Decimal(str(item["cantidad"]))
                * Decimal(str(item["precio_unitario"])),
                categoria=str(item["categoria"]),
            )
            for item in items_finales
        ]
        db.add(db_gasto)
        db.commit()


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