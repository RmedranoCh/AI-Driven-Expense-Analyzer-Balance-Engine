from app.ai.extractor import InvoiceExtractor
from app.ai.classifier import ExpenseClassifier
from app.database.session import get_session, Base, get_engine
from app.database.models import DBGasto, DBGastoItem
from decimal import Decimal
from datetime import datetime, timezone

Base.metadata.create_all(bind=get_engine())

def process_external_invoice(text: str):
    extractor = InvoiceExtractor()
    classifier = ExpenseClassifier()
    
    data = extractor.extract_from_text(text)
    descripciones = [item["descripcion"] for item in data["items"]]
    categorias = classifier.classify_batch(descripciones)
    
    total_gasto = Decimal("0.00")
    db_items = []
    
    for idx, item in enumerate(data["items"]):
        total_linea = item["cantidad"] * item["precio_unitario"]
        total_gasto += total_linea
        
        db_items.append(
            DBGastoItem(
                descripcion=item["descripcion"],
                cantidad=float(item["cantidad"]),
                precio_unitario=float(item["precio_unitario"]),
                total_linea=float(total_linea),
                categoria=categorias[idx] if idx < len(categorias) else "Otros"
            )
        )

    with get_session() as db:
        try:
            db_gasto = DBGasto(
                numero_comprobante=f"EXP-{int(datetime.now(timezone.utc).timestamp())}",
                proveedor=data["proveedor"],
                total_gasto=float(total_gasto)
            )
            for db_item in db_items:
                db_item.gasto = db_gasto
                db_gasto.items.append(db_item)
                
            db.add(db_gasto)
            db.commit()
            print(f"✅ Balance registrado con éxito para: {data['proveedor']}")
        except Exception as e:
            db.rollback()
            print(f"❌ Error al guardar balance: {e}")

if __name__ == "__main__":
    process_external_invoice("Factura de AWS por 2 servidores. Cada uno a 25.00 USD.")