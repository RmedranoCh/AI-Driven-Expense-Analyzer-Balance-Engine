from datetime import date

from expense_analyzer.ai.classifier import ExpenseClassifier
from expense_analyzer.ai.extractor import InvoiceExtractor
from expense_analyzer.database.models import DBGasto
from expense_analyzer.database.session import get_session, initialize_database
from expense_analyzer.dashboard.services import save_approved_invoice
from expense_analyzer.money import to_money

initialize_database()


def process_external_invoice(text: str, user_id: str = "cli_default"):
    extractor = InvoiceExtractor()
    classifier = ExpenseClassifier()

    data = extractor.extract_from_text(text)
    descripciones = [item["descripcion"] for item in data["items"]]
    categorias = classifier.classify_batch(descripciones)

    items = [
        {
            "descripcion": item["descripcion"],
            "cantidad": item["cantidad"],
            "precio_unitario": item["precio_unitario"],
            "categoria": categorias[idx] if idx < len(categorias) else "Otros",
        }
        for idx, item in enumerate(data["items"])
    ]

    if not items:
        print("? No se detectaron items en el texto, nada que registrar.")
        return

    total_gasto = to_money(sum(to_money(i["cantidad"]) * to_money(i["precio_unitario"]) for i in items))

    numero = save_approved_invoice(
        user_id=user_id,
        proveedor=data["proveedor"],
        fecha=date.today(),
        items_finales=items,
        total_recalculado=total_gasto,
    )

    with get_session() as db:
        db_gasto = db.query(DBGasto).filter_by(numero_comprobante=numero).first()
        lineas = db_gasto.items if db_gasto else []

    print(f"? Balance registrado con exito para: {data['proveedor']} ({numero})")
    print(f"  Total: ${total_gasto:,.2f} | Lineas: {len(lineas)}")


if __name__ == "__main__":
    process_external_invoice("Factura de AWS por 2 servidores. Cada uno a 25.00 USD.")
