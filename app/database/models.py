from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .session import Base
from datetime import datetime, timezone

class DBGasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True, index=True)
    numero_comprobante = Column(String, unique=True, index=True)
    proveedor = Column(String, index=True)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_gasto = Column(Numeric(15, 2), nullable=False)
    
    items = relationship("DBGastoItem", back_populates="gasto", cascade="all, delete-orphan")


class DBGastoItem(Base):
    __tablename__ = "gasto_items"

    id = Column(Integer, primary_key=True, index=True)
    gasto_id = Column(Integer, ForeignKey("gastos.id"))
    descripcion = Column(String, nullable=False)
    cantidad = Column(Numeric(12, 4), nullable=False)       
    precio_unitario = Column(Numeric(15, 4), nullable=False) 
    total_linea = Column(Numeric(15, 2), nullable=False)
    categoria = Column(String, default="Otros")
    
    gasto = relationship("DBGasto", back_populates="items")