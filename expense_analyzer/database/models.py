from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .session import Base

CATEGORIA_POR_DEFECTO = "Otros"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DBGasto(Base):
    __tablename__ = "gastos"
    __table_args__ = (
        UniqueConstraint("user_id", "numero_comprobante", name="uq_gasto_usuario_comprobante"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    numero_comprobante = Column(String, index=True)
    proveedor = Column(String, index=True)
    file_hash = Column(String, index=True, nullable=True)
    fecha = Column(DateTime, default=utc_now)
    total_gasto = Column(Numeric(15, 2), nullable=False)
    es_demo = Column(Boolean, nullable=False, default=False, index=True)

    items = relationship(
        "DBGastoItem",
        back_populates="gasto",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DBGastoItem(Base):
    __tablename__ = "gasto_items"

    id = Column(Integer, primary_key=True, index=True)
    gasto_id = Column(Integer, ForeignKey("gastos.id", ondelete="CASCADE"), index=True)
    descripcion = Column(String, nullable=False)
    cantidad = Column(Numeric(12, 4), nullable=False)
    precio_unitario = Column(Numeric(15, 4), nullable=False)
    total_linea = Column(Numeric(15, 2), nullable=False)
    categoria = Column(String, default=CATEGORIA_POR_DEFECTO, index=True)

    gasto = relationship("DBGasto", back_populates="items")


class DBPresupuestoTope(Base):
    __tablename__ = "presupuesto_topes"
    __table_args__ = (
        UniqueConstraint("user_id", "categoria", name="uq_tope_usuario_categoria"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    categoria = Column(String, index=True, nullable=False)
    tope_mensual = Column(Numeric(15, 2), nullable=False)
