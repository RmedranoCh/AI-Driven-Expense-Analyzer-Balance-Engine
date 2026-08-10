# Analizador de Gastos con IA

Aplicación para no perderle el rastro a los gastos de una empresa. Subes una factura en PDF o una foto, y la IA la lee, le asigna una categoría contable a cada concepto y lo muestra todo en un tablero con gráficos y alertas de presupuesto.

---

## Características

- **Lectura de facturas**: la app extrae proveedor, fecha e ítems usando la API de Groq (modelo de visión `qwen/qwen3.6-27b` y de texto `openai/gpt-oss-120b`). Si un PDF no tiene texto extraíble, pasa automáticamente a modo visión.
- **Clasificación contable**: cada ítem se etiqueta con una de estas 9 categorías:

  | Categoría |
  |---|
  | Infraestructura Cloud & Hosting |
  | Herramientas SaaS & Software |
  | Servicios Profesionales & Outsourcing |
  | Marketing, Publicidad & SEO |
  | Hardware & Equipamiento de Oficina |
  | Suscripciones & Educación |
  | Viajes, Viáticos & Transporte |
  | Gastos Operativos Generales |
  | Otros |

  La clasificación se hace en lotes para gastar menos tokens, usando `llama-3.3-70b-versatile` con respuesta en JSON.
- **Tablero (Streamlit + Plotly)**: evolución mensual de gastos, gastos por categoría, distribución por proveedor, métricas rápidas y exportación a Excel multi-hoja.
- **Presupuestos**: topes mensuales por categoría. Si te pasas del límite, la categoría se pinta de rojo.
- **Modo administrador**: con `?admin=1` en la URL puedes cambiar los modelos de IA en caliente, borrar facturas y ver las de todos los usuarios.
- **Datos demo**: al primer arranque carga 4 facturas de ejemplo (AWS, Slack, Meta Ads, Dell) para explorar el tablero sin subir nada.

---

## Tecnologías

| Herramienta | Uso |
|-------------|-----|
| **Streamlit + Plotly** | Tablero y gráficos |
| **Groq API** | IA de extracción y clasificación |
| **openpyxl** | Exportación a Excel |
| **SQLite / PostgreSQL** | Base de datos según el entorno |
| **Docker Compose** | Orquestación del entorno de producción |

---

## Estructura del proyecto

```
expense-analyzer/
├── expense_analyzer/          # Paquete principal
│   ├── ai/                    # Comunicación con Groq (extractor, clasificador)
│   ├── database/              # Modelos ORM y conexión a BD
│   └── dashboard/             # Orquestador, vistas, servicios y estilos
├── data/                      # Base SQLite local (se genera sola, no se versiona)
├── docker/                    # Dockerfile para producción
├── tests/                     # Tests unitarios con pytest
├── streamlit_app.py           # Punto de entrada de Streamlit
├── main.py                    # Punto de entrada por línea de comandos
├── docker-compose.yml         # Orquestación PostgreSQL + app
└── .env.example               # Plantilla de variables de entorno
```

---

## Puesta en marcha

### Con Docker (opcional: entornos locales simulando el de producción)

1. **Requisitos**: Docker y Docker Compose, y una API key de [Groq Cloud](https://groq.com).
2. **Variables de entorno**: crea un archivo `.env` en la raíz con al menos:

   ```ini
   GROQ_API_KEY=tu_clave_de_groq
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Levanta la app**:

   ```bash
   docker compose up -d --build
   ```

   La app queda en `http://localhost:8501`.

### Local (sin Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copia `.env.example` a `.env`, completa `GROQ_API_KEY` y ejecuta:

```bash
streamlit run streamlit_app.py
```

Por defecto usa SQLite. Si quieres PostgreSQL, pon `DATABASE_URL` en el `.env`.

---

## Cómo están modelados los datos

El modelo relacional tiene tres tablas:

- **DBPresupuestoTope**: límites mensuales por categoría.
- **DBGasto**: cabecera de cada factura (proveedor, fecha, total, estado).
- **DBGastoItem**: cada línea de detalle de la factura (descripción, cantidad, precio, categoría).

```
[DBPresupuestoTope]      [DBGasto] ── (1:N) ──► [DBGastoItem]
```

La plata se maneja con `Numeric(15,2)` y toda la aritmética con `Decimal` (redondeo `ROUND_HALF_UP`) para evitar errores de punto flotante.

---

## Flujo de trabajo

1. **Subes** un PDF o imagen desde el panel.
2. **La IA extrae** los datos estructurados (proveedor, fecha, ítems).
3. **La IA clasifica** cada ítem en una categoría.
4. **Revisas y confirmas** antes de guardar.
5. **Se guarda** en la base y los gráficos se actualizan al instante.
6. **El sistema revisa** los topes presupuestarios y te avisa si hace falta.
7. Si aceptas la factura, **queda bloqueada** (no se puede editar ni borrar).

---

## Notas técnicas

- **Precisión financiera**: todo se maneja con `Decimal` en vez de `float`, para no acumular errores de redondeo.
- **Inmutabilidad contable**: una factura marcada como "Aceptado" no se puede modificar ni eliminar; la pista de auditoría queda intacta.
- **Anti duplicados**: cada archivo se hashea con SHA-256; si subes la misma factura dos veces, el sistema lo detecta.
- **Control de costos de API**: límite de facturas por usuario (default 5). El modo admin no tiene límite.
- **Aislamiento por usuario**: cada navegador tiene un ID único (`?uid=...`) y los datos están separados por usuario.
- **SQLite en dev, PostgreSQL en producción**: el sistema elige la base según la configuración.

---

## Tests

```bash
docker compose exec app pytest tests/unit -v
```

Los tests cubren la consolidación y precisión financiera, los modelos ORM, la extracción y saneamiento de datos, la clasificación por categorías y las utilidades compartidas.

---

## Licencia

Uso interno. Proyecto personal de gestión financiera empresarial.

---

¿Lo prefieres en inglés? → [README.en.md](README.en.md)