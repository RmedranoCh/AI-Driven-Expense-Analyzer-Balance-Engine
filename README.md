# AI-Driven Expense Analyzer & Balance Engine

Un asistente inteligente para controlar los gastos de tu empresa. Subí una factura en PDF o una foto, y el sistema se encarga de leerla con inteligencia artificial, clasificar cada concepto en categorías contables, y mostrarte todo en un tablero interactivo con gráficos yalertas presupuestarias.

---

## ¿Qué hace esto?

Cargás un comprobante (PDF o imagen), la IA lo procesa, extrae proveedor, fecha y detalle de ítems, clasifica automáticamente cada línea en una categoría financiera, y lo guarda en la base de datos. Después podés ver gráficos de evolución mensual, controlar topes por categoría y exportar todo a Excel.

---

## Cómo empezar

### Opción 1: Con Docker (recomendado para producción)

1. **Requisitos:** Docker y Docker Compose instalados, una API Key de [Groq Cloud](https://groq.com).

2. **Configurar variables de entorno:** Creá un archivo `.env` en la raíz del proyecto con este contenido mínimo:

   ```ini
   GROQ_API_KEY=tu_clave_de_groq
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Levantar todo:**

   ```bash
   docker compose up -d --build
   ```

   La app arranca en `http://localhost:8501`.

4. **Ejecutar pruebas:**

   ```bash
   docker compose exec app pytest tests/unit/test_engine.py -v
   ```

### Opción 2: Local (sin Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copiá `.env.example` a `.env`, completá `GROQ_API_KEY`, y ejecutá:

```bash
streamlit run streamlit_app.py
```

La app usa SQLite por defecto. Si querés PostgreSQL, configura `DATABASE_URL` en el `.env`.

---

## Funcionalidades

### Carga inteligente de facturas
Subís un PDF o imagen, y el sistema extrae automáticamente el proveedor, la fecha y los ítems usando la API de Groq con modelos de visión (`qwen/qwen3.6-27b`) y texto (`openai/gpt-oss-120b`). Si un PDF no tiene texto extraíble, automáticamente fallbackea a procesamiento por visión.

### Clasificación por categorías
Cada ítem se etiqueta con una de 9 categorías:

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

Esto se hace en lotes (batch NLP) para ahorrar tokens y reducir latencia, usando el modelo `llama-3.3-70b-versatile` con respuesta forzada en JSON.

### Panel interactivo (Streamlit + Plotly)
- Evolución mensual de gastos (gráfico de líneas)
- Gastos por categoría (barras)
- Distribución por proveedor (torta)
- Métricas rápidas: total filtrado, cantidad de conceptos, proveedores distintos
- Exportación a Excel multi-hoja (.xlsx)

### Control presupuestario
Configurás topes mensuales por categoría y el sistema te alerta visualmente cuando estás por excederte. Si te pasás del límite, la categoría se marca en rojo.

### Modo administrador
Agregá `?admin=1` a la URL y entrás con tu contraseña. Desde ahí podés:
- Cambiar los modelos de IA en caliente
- Depurar facturas individuales
- Ver facturas de todos los usuarios (sin límite por usuario)

### Datos de demostración
La primera vez que arrancás la app, se cargan automáticamente 4 facturas de ejemplo (AWS, Slack, Meta Ads, Dell) para que puedas explorar el tablero sin tener que subir nada.

---

## Estructura del proyecto

```
expense-analyzer/
├── app/
│   ├── ai/
│   │   ├── extractor.py          # Extraer datos de facturas (PDF/imagen) con Groq
│   │   └── classifier.py         # Clasificar ítems en categorías con Groq
│   ├── dashboard/
│   │   └── main_ui.py            # Interfaz completa de Streamlit
│   └── database/
│       ├── models.py             # Modelos ORM: DBGasto, DBGastoItem, DBPresupuestoTope
│       └── session.py            # Conexión a BD (SQLite o PostgreSQL)
├── docker/
│   └── Dockerfile                # Imagen Docker para producción
├── tests/
│   └── unit/
│       └── test_engine.py        # Pruebas de consolidación y precisión financiera
├── docker-compose.yml            # Orquestación PostgreSQL + app
├── streamlit_app.py              # Punto de entrada de Streamlit
├── main.py                       # Punto de entrada por línea de comandos
├── requirements.txt              # Dependencias de Python
└── .env.example                  # Plantilla de variables de entorno
```

---

## Arquitectura de datos

El modelo relacional tiene tres tablas principales:

- **DBPresupuestoTope**: guarda los límites mensuales por categoría.
- **DBGasto**: cabecera de cada factura (proveedor, fecha, total, estado).
- **DBGastoItem**: líneas de detalle de cada factura (descripción, cantidad, precio, categoría).

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

Los campos monetarios usan `Numeric(15,2)`, y toda la aritmética se hace con `Decimal` de Python con redondeo `ROUND_HALF_UP`, evitando errores de punto flotante.

---

## Flujo de trabajo

1. **Subís** un PDF o imagen desde el panel.
2. **La IA extrae** los datos estructurados (proveedor, fecha, ítems).
3. **La IA clasifica** cada ítem en una categoría.
4. **Revisás y confirmás** los datos antes de guardarlos.
5. **Se guarda** en la base de datos y se actualizan los gráficos al instante.
6. **El sistema verifica** topes presupuestarios y te alerta si corresponde.
7. Si aceptás la factura, **queda bloqueada** (no se puede editar ni borrar).

---

## Decisiones técnicas importantes

- **Precisión financiera:** todo se maneja con `Decimal` en vez de `float` para evitar errores de redondeo acumulativos.
- **Inmutabilidad contable:** una vez que una factura se marca como "Aceptado", no se puede modificar ni eliminar, garantizando la integridad de la pista de auditoría.
- **Protección contra duplicados:** cada archivo se hashea con SHA-256; si volvés a subir la misma factura, el sistema lo detecta.
- **Control de costos de API:** hay un límite configurable de facturas por usuario (default 5) para no abusar de Groq. El modo admin no tiene límite.
- **Aislamiento por usuario:** cada navegador tiene un ID único (`?uid=...`), y los datos están separados por usuario.
- **SQLite en desarrollo, PostgreSQL en producción:** el sistema detecta automáticamente qué base usar según la configuración.

---

## Licencia

Uso interno. Proyecto personal con fines de gestión financiera empresarial.

---

---

# AI-Driven Expense Analyzer & Balance Engine

An intelligent assistant to keep your company's expenses under control. Upload a PDF invoice or a picture, and the system reads it with artificial intelligence, classifies each line item into financial categories, and displays everything in an interactive dashboard with charts and budget alerts.

---

## What does it do?

You upload a receipt (PDF or image), the AI processes it, extracts the vendor, date, and line items, automatically classifies each line into a financial category, and saves it to the database. You can then view monthly trend charts, monitor budget caps per category, and export everything to Excel.

---

## Getting started

### Option 1: Docker (recommended for production)

1. **Prerequisites:** Docker and Docker Compose installed, and a [Groq Cloud](https://groq.com) API key.

2. **Environment variables:** Create a `.env` file in the project root with at least:

   ```ini
   GROQ_API_KEY=your_groq_key
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Launch everything:**

   ```bash
   docker compose up -d --build
   ```

   The app will be available at `http://localhost:8501`.

4. **Run tests:**

   ```bash
   docker compose exec app pytest tests/unit/test_engine.py -v
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

The app uses SQLite by default. If you want PostgreSQL, set `DATABASE_URL` in your `.env`.

---

## Features

### Smart invoice ingestion
Upload a PDF or image, and the system automatically extracts the vendor, date, and line items using the Groq API with vision models (`qwen/qwen3.6-27b`) and text models (`openai/gpt-oss-120b`). If a PDF has no extractable text, it automatically falls back to vision processing.

### Category classification
Each item is tagged with one of 9 categories:

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

This is done in batches (batch NLP) to save tokens and reduce latency, using the `llama-3.3-70b-versatile` model with forced JSON responses.

### Interactive dashboard (Streamlit + Plotly)
- Monthly expense trends (line chart)
- Expenses by category (bar chart)
- Distribution by vendor (pie chart)
- Quick metrics: total filtered spend, concept count, distinct vendors
- Multi-sheet Excel export (.xlsx)

### Budget control
Set monthly caps per category and get visual alerts when you are about to exceed them. Categories that exceed their limit are highlighted in red.

### Admin mode
Add `?admin=1` to the URL and log in with your password. From there you can:
- Swap AI models on the fly
- Purge individual invoices
- View all users' invoices (no per-user limit)

### Demo data
On first launch, the app automatically seeds 4 sample invoices (AWS, Slack, Meta Ads, Dell) so you can explore the dashboard without uploading anything.

---

## Project structure

```
expense-analyzer/
├── app/
│   ├── ai/
│   │   ├── extractor.py          # Extract invoice data (PDF/image) via Groq
│   │   └── classifier.py         # Classify items into categories via Groq
│   ├── dashboard/
│   │   └── main_ui.py            # Complete Streamlit interface
│   └── database/
│       ├── models.py             # ORM models: DBGasto, DBGastoItem, DBPresupuestoTope
│       └── session.py            # DB connection (SQLite or PostgreSQL)
├── docker/
│   └── Dockerfile                # Production Docker image
├── tests/
│   └── unit/
│       └── test_engine.py        # Consolidation and financial precision tests
├── docker-compose.yml            # PostgreSQL + app orchestration
├── streamlit_app.py              # Streamlit entry point
├── main.py                       # CLI entry point
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variable template
```

---

## Data architecture

The relational model has three main tables:

- **DBPresupuestoTope**: stores monthly limits per category.
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

Monetary fields use `Numeric(15,2)`, and all arithmetic uses Python's `Decimal` with `ROUND_HALF_UP` rounding, avoiding floating-point errors.

---

## Workflow

1. **You upload** a PDF or image from the dashboard.
2. **The AI extracts** structured data (vendor, date, items).
3. **The AI classifies** each item into a category.
4. **You review and confirm** the data before saving.
5. **It gets saved** to the database and the charts update instantly.
6. **The system checks** budget caps and alerts you if needed.
7. If you accept the invoice, **it becomes locked** (cannot be edited or deleted).

---

## Key technical decisions

- **Financial precision:** everything uses `Decimal` instead of `float` to avoid cumulative rounding errors.
- **Accounting immutability:** once an invoice is marked as "Accepted", it cannot be modified or deleted, guaranteeing audit trail integrity.
- **Duplicate protection:** each file is hashed with SHA-256; re-uploading the same invoice is detected automatically.
- **API cost control:** a configurable per-user invoice limit (default 5) prevents excessive Groq usage. Admin mode bypasses this limit.
- **Per-user isolation:** each browser session gets a unique ID (`?uid=...`), and data is scoped per user.
- **SQLite in development, PostgreSQL in production:** the system auto-detects which database to use based on configuration.

---

## License

Internal use. Personal project for business financial management purposes.
