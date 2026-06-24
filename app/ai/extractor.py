import os
import json
import base64
from datetime import datetime
import streamlit as st
from groq import Groq
from decimal import Decimal

def _get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        raise RuntimeError("GROQ_API_KEY not found in env or Streamlit secrets")

class InvoiceExtractor:
    def __init__(self, vision_model: str = None, text_model: str = None):
        self.client = Groq(api_key=_get_groq_key())
        self.vision_model = vision_model or "qwen/qwen3.6-27b"
        self.text_model = text_model or "llama-3.3-70b-versatile"

    def extract_from_text(self, text: str) -> dict:
        prompt = f"""
        Analiza el texto de esta factura externa y extrae los datos de egreso.
        Responde ÚNICAMENTE con un objeto JSON válido, sin bloques de formato markdown.

        REGLA CRÍTICA PARA EL PROVEEDOR:
        Identifica con precisión al EMISOR REAL del gasto o comercio que vende el producto/servicio.
        Si la factura es un comprobante de transacciones bancarias, pasarelas de pago (ej. Banco Unión, PayPal, Stripe) 
        o facturas emitidas a través de un banco hacia una persona/comercio, NO extraigas el nombre del banco como proveedor.
        En su lugar, localiza el nombre del comercio, vendedor o tercero real que originó el cobro del gasto.

        REGLA PARA LA FECHA:
        Extrae la fecha de emisión de la factura (NO la fecha actual). Si no encuentras fecha, usa null.

        Esquema esperado:
        {{
            "proveedor": "Nombre del Vendedor/Comercio Real",
            "fecha": "YYYY-MM-DD o null si no se encuentra",
            "items": [
                {{
                    "descripcion": "Descripción del concepto",
                    "cantidad": 1.0,
                    "precio_unitario": 0.00
                }}
            ]
        }}

        Texto:
        {text}
        """
        return self._call_groq([{"role": "user", "content": prompt}], self.text_model)

    def extract_from_image(self, image_bytes: bytes, mime_type: str) -> dict:
        prompt = """
        Analiza visualmente esta factura externa de compra.
        Responde EXCLUSIVAMENTE con un JSON que contenga las llaves:
        - "proveedor" (string)
        - "fecha" (string en formato YYYY-MM-DD, o null si no se encuentra fecha)
        - "items" (lista de objetos con: "descripcion", "cantidad", "precio_unitario").

        REGLA CRÍTICA PARA EL PROVEEDOR:
        Extrae el nombre del negocio o persona física que vende o presta el servicio. 
        Si el documento es un formato preimpreso de una entidad financiera (ej. Banco Unión) pero detalla una transacción 
        u operación comercial hacia/desde un tercero o cliente, prioriza el nombre del comercio o titular real del servicio, 
        evitando colocar las siglas del banco intermediario como proveedor.

        REGLA PARA LA FECHA:
        Extrae la fecha de emisión de la factura visible en el documento (NO la fecha actual).
        """
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            }
        ]
        return self._call_groq(messages, self.vision_model)

    def _call_groq(self, messages, model) -> dict:
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return self._sanitize_json_data(json.loads(response.choices[0].message.content))
        except Exception as e:
            print(f"❌ Error en Groq: {e}")
            raise e

    def _sanitize_json_data(self, raw_data: dict) -> dict:
        def clean_decimal(v):
            if v is None: return Decimal("0.00")
            clean_str = ''.join(c for c in str(v).replace('$', '').replace(',', '').strip() if c.isdigit() or c == '.')
            try: return Decimal(clean_str) if clean_str else Decimal("0.00")
            except Exception: return Decimal("0.00")

        def parse_date(v):
            if not v or str(v).lower() in ("null", "none", ""):
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"):
                try:
                    return datetime.strptime(str(v).strip(), fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return None

        return {
            "proveedor": str(raw_data.get("proveedor", raw_data.get("cliente", "Desconocido"))),
            "fecha": parse_date(raw_data.get("fecha")),
            "items": [
                {
                    "descripcion": str(item.get("descripcion", "Concepto General")),
                    "cantidad": clean_decimal(item.get("cantidad", 1)),
                    "precio_unitario": clean_decimal(item.get("precio_unitario", 0))
                } for item in raw_data.get("items", [])
            ]
        }