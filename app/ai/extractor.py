import os
import json
import base64
from groq import Groq
from decimal import Decimal

class InvoiceExtractor:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.text_model = "llama-3.3-70b-versatile"

    def extract_from_text(self, text: str) -> dict:
        prompt = f"""
        Analiza el texto de esta factura externa y extrae los datos de egreso.
        Responde ÚNICAMENTE con un objeto JSON válido, sin bloques de formato markdown.

        REGLA CRÍTICA PARA EL PROVEEDOR:
        Identifica con precisión al EMISOR REAL del gasto o comercio que vende el producto/servicio.
        Si la factura es un comprobante de transacciones bancarias, pasarelas de pago (ej. Banco Unión, PayPal, Stripe) 
        o facturas emitidas a través de un banco hacia una persona/comercio, NO extraigas el nombre del banco como proveedor.
        En su lugar, localiza el nombre del comercio, vendedor o tercero real que originó el cobro del gasto.

        Esquema esperado:
        {{
            "proveedor": "Nombre del Vendedor/Comercio Real (Evitar nombres de intermediarios bancarios si el gasto es de un tercero)",
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
        - "items" (lista de objetos con: "descripcion", "cantidad", "precio_unitario").

        REGLA CRÍTICA PARA EL PROVEEDOR:
        Extrae el nombre del negocio o persona física que vende o presta el servicio. 
        Si el documento es un formato preimpreso de una entidad financiera (ej. Banco Unión) pero detalla una transacción 
        u operación comercial hacia/desde un tercero o cliente, prioriza el nombre del comercio o titular real del servicio, 
        evitando colocar las siglas del banco intermediario como proveedor.
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

        return {
            "proveedor": str(raw_data.get("proveedor", raw_data.get("cliente", "Desconocido"))),
            "items": [
                {
                    "descripcion": str(item.get("descripcion", "Concepto General")),
                    "cantidad": clean_decimal(item.get("cantidad", 1)),
                    "precio_unitario": clean_decimal(item.get("precio_unitario", 0))
                } for item in raw_data.get("items", [])
            ]
        }