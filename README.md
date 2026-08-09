# Analizador de Gastos con IA

App para no perderle el rastro a los gastos de la empresa. Subís una factura en PDF o una foto y la IA la lee, le asigna categoría contable a cada concepto y te lo muestra todo en un tablero con gráficos y alertas de presupuesto.

---

## Qué hace

Subís un comprobante (PDF o imagen), la IA saca el proveedor, la fecha y los ítems, clasifica cada línea en una categoría financiera y lo guarda en la base de datos. Después tenés gráficos de evolución mensual, podés fijar topes por categoría y exportar todo a Excel.

---

## Cómo correrlo

### Con Docker (recomendado para producción)

1. **Requisitos:** Docker y Docker Compose, y una API key de [Groq Cloud](https://groq.com).

2. **Variables de entorno:** creá un archivo `.env` en la raíz con esto como mínimo:

   ```ini
   GROQ_API_KEY=tu_clave_de_groq
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Levantalo:**

   ```bash
   docker compose up -d --build
   ```

   La app queda en `http://localhost:8501`.

4. **Correr los tests:**

   ```bash
   docker compose exec app pytest tests/unit -v
   ```

### Sin Docker (local)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copiá `.env.example` a `.env`, completá `GROQ_API_KEY` y ejecutá:

```bash
streamlit run streamlit_app.py
```

Por defecto usa SQLite. Si querés PostgreSQL, poné `DATABASE_URL` en el `.env`.

---

## Funcionalidades

### Lectura de facturas
Subís un PDF o una foto y la app extrae proveedor, fecha e ítems con la API de Groq (modelo de visión `qwen/qwen3.6-27b` y de texto `openai/gpt-oss-120b`). Si el PDF no tiene texto que se pueda extraer, automáticamente pasa a modo visión.

### Categorías
Cada ítem se etiqueta con una de estas 9 categorías:

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

La clasificación se hace en lotes (batch) para gastar menos tokens y tardar menos, usando `llama-3.3-70b-versatile` pidiéndole siempre la respuesta en JSON.

### Panel (Streamlit + Plotly)
- Evolución mensual de gastos (gráfico de líneas)
- Gastos por categoría (barras)
- Distribución por proveedor (torta)
- Métricas rápidas: total filtrado, cantidad de conceptos, proveedores distintos
- Exportación a Excel multi-hoja (.xlsx)

### Presupuestos
Ponés topes mensuales por categoría y la app te avisa visualmente cuando estás por pasarte. Si te pasás del límite, la categoría se pinta de rojo.

### Modo administrador
Agregá `?admin=1` a la URL y entrás con tu contraseña. Desde ahí podés:
- Cambiar los modelos de IA en caliente
- Borrar facturas individuales
- Ver las facturas de todos los usuarios (sin el límite por usuario)

### Datos demo
La primera vez que arranca la app carga 4 facturas de ejemplo (AWS, Slack, Meta Ads, Dell) para que puedas explorar el tablero sin subir nada.

---

## Estructura del proyecto

```
expense-analyzer/
├── expense_analyzer/              # Paquete principal
│   ├── ai/                        # Todo lo que habla con Groq
│   │   ├── extractor.py           # Extrae datos de facturas (PDF/imagen)
│   │   ├── classifier.py          # Clasifica ítems en categorías
│   │   └── _common.py             # Cliente compartido de Groq
│   ├── database/                  # Acceso a datos
│   │   ├── models.py              # Modelos ORM: DBGasto, DBGastoItem, DBPresupuestoTope
│   │   └── session.py             # Conexión a BD (SQLite o PostgreSQL)
│   └── dashboard/                 # Todo lo que se ve en pantalla
│       ├── app.py                 # Orquestador: ExpenseDashboard
│       ├── views.py               # Renderizado: stats, presupuesto, confirmación
│       ├── services.py            # Lógica de negocio y acceso a datos
│       └── styles.py              # CSS y configuración visual
├── data/                          # Base SQLite local (se genera sola, no se versiona)
├── docker/
│   └── Dockerfile                 # Imagen Docker para producción
├── tests/
│   ├── conftest.py                # Fixtures compartidos
│   └── unit/
│       ├── test_engine.py         # Consolidación y precisión financiera
│       ├── test_models.py         # Modelos ORM
│       ├── test_extractor.py      # Extracción y saneamiento de datos
│       ├── test_classifier.py     # Clasificación por categorías
│       └── test_common.py         # Utilidades compartidas
├── docker-compose.yml             # Orquestación PostgreSQL + app
├── streamlit_app.py               # Punto de entrada de Streamlit
├── main.py                        # Punto de entrada por línea de comandos
├── requirements.txt               # Dependencias de Python
└── .env.example                   # Plantilla de variables de entorno
```

---

## Cómo están modelados los datos

El modelo relacional tiene tres tablas:

- **DBPresupuestoTope**: los límites mensuales por categoría.
- **DBGasto**: cabecera de cada factura (proveedor, fecha, total, estado).
- **DBGastoItem**: cada línea de detalle de la factura (descripción, cantidad, precio, categoría).

```
[DBPresupuestoTope]         [DBGasto] ─── (1:N) ───► [DBGastoItem]
   categoria (PK)              id (PK)                  id (PK)
   tope_mensual                numero_comprobante        gasto_id (FK)
                               proveedor                 descripcion
                               fecha                     cantidad
                               total_gasto               precio_unitario
                               estado                    total_linea
                                                         categoria
```

La plata se maneja con `Numeric(15,2)` y toda la aritmética con `Decimal` (redondeo `ROUND_HALF_UP`) para no comerse errores de punto flotante.

---

## Flujo de trabajo

1. **Subís** un PDF o imagen desde el panel.
2. **La IA extrae** los datos estructurados (proveedor, fecha, ítems).
3. **La IA clasifica** cada ítem en una categoría.
4. **Revisás y confirmás** los datos antes de guardarlos.
5. **Se guarda** en la base y los gráficos se actualizan al toque.
6. **El sistema chequea** los topes presupuestarios y te avisa si hace falta.
7. Si aceptás la factura, **queda bloqueada** (no se puede editar ni borrar).

---

## Notas técnicas

- **Precisión financiera:** todo se maneja con `Decimal` en vez de `float`, para no acumular errores de redondeo.
- **Inmutabilidad contable:** una factura marcada como "Aceptado" no se puede modificar ni eliminar, así queda intacta la pista de auditoría.
- **Anti duplicados:** cada archivo se hashea con SHA-256; si volvés a subir la misma factura, el sistema lo detecta.
- **Control de costos de API:** hay un límite de facturas por usuario (default 5) para no abusar de Groq. El modo admin no tiene límite.
- **Aislamiento por usuario:** cada navegador tiene un ID único (`?uid=...`) y los datos están separados por usuario.
- **SQLite en dev, PostgreSQL en producción:** el sistema elige sola qué base usar según la configuración.

---

## Licencia

Uso interno. Proyecto personal de gestión financiera empresarial.

---

# Analizador de Gastos con IA (English)

App to keep an eye on company expenses without going crazy. Upload a PDF invoice or a picture, and the AI reads it, assigns an accounting category to each line item, and shows everything in a dashboard with charts and budget alerts.

---

## What it does

You upload a receipt (PDF or image), the AI pulls the vendor, date and line items, classifies each line into a financial category, and stores it in the database. Then you can look at monthly trends, set caps per category, and export everything to Excel.

---

## Getting started

### Option 1: Docker (recommended for production)

1. **Prerequisites:** Docker and Docker Compose, plus a [Groq Cloud](https://groq.com) API key.

2. **Environment variables:** create a `.env` file in the project root with at least:

   ```ini
   GROQ_API_KEY=your_groq_key
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Launch it:**

   ```bash
   docker compose up -d --build
   ```

   The app will be at `http://localhost:8501`.

4. **Run the tests:**

   ```bash
   docker compose exec app pytest tests/unit -v
   ```

### Option 2: Local (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill in `GROQ_API_KEY`, and run:

```bash
streamlit run streamlit_app.py
```

It uses SQLite by default. If you want PostgreSQL, set `DATABASE_URL` in your `.env`.

---

## Features

### Smart invoice reading
Upload a PDF or image and the app extracts the vendor, date and items using the Groq API (vision model `qwen/qwen3.6-27b`, text model `openai/gpt-oss-120b`). If a PDF has no extractable text, it automatically falls back to vision processing.

### Categories
Each item gets tagged with one of these 9 categories:

| Category |
|---|
| Cloud Infrastructure & Hosting |
| SaaS Tools & Software |
| Professional Services & Outsourcing |
| Marketing, Advertising & SEO |
| Hardware & Office Equipment |
| Subscriptions & Education |
| Travel, Per Diem & Transportation |
| General Operating Expenses |
| Others |

Classification runs in batches to save tokens and reduce latency, using `llama-3.3-70b-versatile` with forced JSON responses.

### Dashboard (Streamlit + Plotly)
- Monthly expense trends (line chart)
- Expenses by category (bar chart)
- Share by vendor (pie chart)
- Quick metrics: filtered total, concept count, distinct vendors
- Multi-sheet Excel export (.xlsx)

### Budget control
Set monthly caps per category and get visual warnings when you're about to go over. Categories over their limit turn red.

### Admin mode
Add `?admin=1` to the URL and log in with your password. From there you can:
- Swap AI models on the fly
- Delete individual invoices
- See every user's invoices (no per-user limit)

### Demo data
On first launch, the app seeds 4 sample invoices (AWS, Slack, Meta Ads, Dell) so you can poke around the dashboard without uploading anything.

---

## Project structure

```
expense-analyzer/
├── expense_analyzer/              # Main package
│   ├── ai/                        # Everything that talks to Groq
│   │   ├── extractor.py           # Extracts invoice data (PDF/image)
│   │   ├── classifier.py          # Classifies items into categories
│   │   └── _common.py             # Shared Groq client
│   ├── database/                  # Data access
│   │   ├── models.py              # ORM models: DBGasto, DBGastoItem, DBPresupuestoTope
│   │   └── session.py             # DB connection (SQLite or PostgreSQL)
│   └── dashboard/                 # Everything you see on screen
│       ├── app.py                 # Orchestrator: ExpenseDashboard
│       ├── views.py               # Rendering: stats, budget, confirmation
│       ├── services.py            # Business logic and data access
│       └── styles.py              # CSS and visual config
├── data/                          # Local SQLite DB (auto-generated, not versioned)
├── docker/
│   └── Dockerfile                 # Production Docker image
├── tests/
│   ├── conftest.py                # Shared fixtures
│   └── unit/
│       ├── test_engine.py         # Consolidation and financial precision
│       ├── test_models.py         # ORM models
│       ├── test_extractor.py      # Extraction and sanitization
│       ├── test_classifier.py     # Category classification
│       └── test_common.py         # Shared utilities
├── docker-compose.yml             # PostgreSQL + app orchestration
├── streamlit_app.py               # Streamlit entry point
├── main.py                        # CLI entry point
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment variable template
```

---

## Data architecture

The relational model has three tables:

- **DBPresupuestoTope**: monthly limits per category.
- **DBGasto**: invoice header (vendor, date, total, status).
- **DBGastoItem**: line items for each invoice (description, quantity, price, category).

```
[DBPresupuestoTope]         [DBGasto] ─── (1:N) ───► [DBGastoItem]
   categoria (PK)              id (PK)                  id (PK)
   tope_mensual                numero_comprobante        gasto_id (FK)
                               proveedor                 descripcion
                               fecha                     cantidad
                               total_gasto               precio_unitario
                               estado                    total_linea
                                                         categoria
```

Money is stored as `Numeric(15,2)` and all math runs on Python `Decimal` with `ROUND_HALF_UP`, so floating-point errors never sneak in.

---

## Workflow

1. **You upload** a PDF or image from the dashboard.
2. **The AI extracts** structured data (vendor, date, items).
3. **The AI classifies** each item into a category.
4. **You review and confirm** before saving.
5. **It gets saved** to the database and the charts update instantly.
6. **The system checks** budget caps and alerts you if needed.
7. If you accept the invoice, **it locks** (can't be edited or deleted).

---

## Technical notes

- **Financial precision:** everything uses `Decimal` instead of `float` so rounding errors don't pile up.
- **Accounting immutability:** once an invoice is marked "Accepted", it can't be modified or deleted, keeping the audit trail intact.
- **Duplicate protection:** every file is hashed with SHA-256; re-uploading the same invoice gets caught automatically.
- **API cost control:** a configurable per-user invoice limit (default 5) keeps Groq usage in check. Admin mode bypasses it.
- **Per-user isolation:** each browser session gets a unique ID (`?uid=...`) and data is scoped per user.
- **SQLite in dev, PostgreSQL in prod:** the system picks the database by itself based on the config.

---

## License

Internal use. Personal project for business financial management.
