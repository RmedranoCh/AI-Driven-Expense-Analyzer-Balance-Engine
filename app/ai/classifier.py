import os
import json
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from typing import List

load_dotenv()

def _get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        raise RuntimeError("GROQ_API_KEY not found in env or Streamlit secrets")

class ExpenseClassifier:    
    def __init__(self, model: str = None):
        self.client = Groq(api_key=_get_groq_key())
        self.model = model or "openai/gpt-oss-120b"
        self.categorias_validas = [
            "Infraestructura Cloud & Hosting", 
            "Herramientas SaaS & Software",
            "Servicios Profesionales & Outsourcing", 
            "Marketing, Publicidad & SEO", 
            "Hardware & Equipamiento de Oficina", 
            "Suscripciones & Educación",
            "Viajes, Viáticos & Transporte", 
            "Gastos Operativos Generales", 
            "Otros"
        ]

    def classify_batch(self, descripciones: List[str]) -> List[str]:
        if not descripciones:
            return []

        lista_items = "\n".join([f"ID:{i} - {desc}" for i, desc in enumerate(descripciones)])
        
        prompt = f"""
        Clasifica rigurosamente cada concepto por su ID en una de estas categorías financieras:
        {', '.join(self.categorias_validas)}.

        Responde ÚNICAMENTE con un JSON compacto y estructurado tal como este ejemplo:
        {{
            "clasificaciones": [
                {{"item_id": 0, "categoria": "Nombre Exacto de la Categoría"}}
            ]
        }}

        Conceptos a clasificar:
        {lista_items}
        """

        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            raw_response = json.loads(content)
            clasificaciones = raw_response.get("clasificaciones", [])
            
            mapeo_ia = {item["item_id"]: item["categoria"] for item in clasificaciones}
            
            resultado = []
            for i in range(len(descripciones)):
                cat_detectada = mapeo_ia.get(i, "Otros")
                if cat_detectada in self.categorias_validas:
                    resultado.append(cat_detectada)
                else:
                    resultado.append("Otros")
            return resultado

        except Exception as e:
            print(f"❌ Error en clasificación en lote: {e}")
            return ["Otros"] * len(descripciones)