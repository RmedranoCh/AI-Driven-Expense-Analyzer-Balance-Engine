# 📊 AI-Driven Expense Analyzer & Balance Engine

Un motor inteligente de análisis de egresos, control presupuestario y consolidación contable desarrollado en **Python 3.11**. El sistema automatiza la ingesta de comprobantes externos (PDFs e imágenes) mediante modelos fundacionales de visión artificial (OCR/VLM), categoriza los conceptos a través de procesamiento de lenguaje natural en lote (Batch NLP) y centraliza métricas clave en un panel analítico en tiempo real en un entorno totalmente contenerizado con Docker.

Este proyecto migró arquitectónicamente de un emisor de facturas propio a una plataforma robusta de **auditoría de gastos corporativos externos, gobernanza presupuestaria y balances consolidados**.

---

## 🛠️ Stack Tecnológico y Decisiones de Ingeniería

*   **Core Financiero e Integridad:** Implementación estricta de aritmética con `Decimal` (módulo `decimal` nativo de Python) con políticas de redondeo financiero `ROUND_HALF_UP`. Se evitó por completo el uso de tipos flotantes de precisión binaria (`float`) para asegurar inmunidad frente a errores acumulativos de redondeo contable.
*   **Gobernanza Contable (Inmutabilidad):** Sistema estricto de estados de transacción. Una vez que un comprobante o factura es marcado como **Aceptado**, el motor bloquea cualquier intento de edición, modificación o actualización de sus campos, garantizando una auditoría interna inalterable y conforme a estándares contables de control.
*   **Gestión del Ciclo de Vida:** Capacidad integrada para la eliminación segura de comprobantes rechazados o duplicados, actualizando dinámicamente los balances contables, el historial de auditoría y liberando inmediatamente el presupuesto consumido en el mes.
*   **Control Presupuestario Dinámico (Topes Mensuales):** Módulo de validación de políticas financieras que permite configurar límites financieros máximos mensuales por categoría contable. El sistema evalúa en tiempo real cada factura entrante frente al acumulado mensual de su categoría, alertando visualmente o restringiendo el registro ante desbordamientos presupuestarios.
*   **Capa de Inteligencia Artificial (Multimodal):** Pipeline de extracción asíncrono con **Groq API** utilizando `meta-llama/llama-4-scout-17b-16e-instruct` para análisis de visión sobre imágenes y `llama-3.3-70b-versatile` para extracción de entidades desde texto [1].
*   **Batch NLP Classification:** Módulo optimizado de clasificación por lotes que agrupa descripciones crudas de ítems bajo una taxonomía estricta de 9 categorías operativas corporativas, reduciendo latencias y optimizando costos de tokens mediante respuestas forzadas en esquemas `json_object`.
*   **Persistencia y Seguridad:** Capa de datos con **SQLAlchemy ORM** y **PostgreSQL 15**. Arquitectura relacional estricta mapeada con campos `Numeric(15,2)`. Motor configurado con políticas `pool_pre_ping=True` para tolerancia a fallos de red y reintentos automatizados en caliente.
*   **Visualización de Datos:** Centro de operaciones interactivo implementado con **Streamlit**, gráficos analíticos avanzados con **Plotly Express** (líneas de tendencia mensual, medidores de tope presupuestario por categoría y participación de mercado de proveedores) y exportador en memoria nativo a **Excel (.xlsx)** estructurado multi-hoja a través de bytes (`io.BytesIO`) y `openpyxl`.
*   **DevOps y Contenerización:** Orquestación multifase estructurada con **Docker** y **Docker Compose**. Incluye mecanismos de `healthcheck` que postergan el inicio del servidor de la aplicación hasta asegurar el estado óptimo de aceptación de sockets en la base de datos.

---

## 📐 Arquitectura de Datos (Modelado Contable)

El esquema relacional mitiga la redundancia, gestiona el estado de inmutabilidad y almacena las reglas de topes presupuestarios de la siguiente manera:

```text
  [DBPresupuestoTope]                    [DBGasto (Cabecera)] ─── (1:N) ───► [DBGastoItem (Líneas del Detalle)]
  ├── categoria (PK, Indexado)           ├── id (PK)                          ├── id (PK)
  └── tope_mensual (Numeric 15,2)        ├── numero_comprobante (Unique UUID)  ├── gasto_id (FK)
                                         ├── proveedor (Indexado)              ├── descripcion
                                         ├── fecha (UTC Timestamp)             ├── cantidad (Numeric 12,4)
                                         ├── total_gasto (Numeric 15,2)        ├── precio_unitario (Numeric 15,4)
                                         └── estado (Enum: Borrador, Aceptado) ├── total_linea (Numeric 15,2)
                                                                               └── categoria (Indexado)
```

---

## 🚀 Guía de Despliegue Rápido (Producción)

### Prerrequisitos
*   Docker y Docker Compose instalados globalmente.
*   Una API Key válida de Groq Cloud.

### 1. Variables de Entorno
Crea un archivo `.env` en el directorio raíz del proyecto con la siguiente estructura:

```ini
GROQ_API_KEY=tu_clave_secreta_de_groq
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=invoice_engine_db
DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
```

### 2. Levantamiento de la Infraestructura
Ejecuta el pipeline de construcción de Docker sin usar el caché para garantizar imágenes limpias e inmutables:

```bash
# Construir e inicializar servicios en segundo plano
docker compose up -d --build

# Monitorear logs de la IA y conexiones a la Base de Datos
docker compose logs -f app
```

El panel analítico se desplegará inmediatamente en la dirección: `http://localhost:8501`.

### 3. Suite de Pruebas Unitarias
Para validar de forma independiente el algoritmo de consolidación, las restricciones de inmutabilidad, las alertas de topes presupuestarios y la precisión del redondeo financiero:

```bash
docker compose exec app pytest tests/unit/test_engine.py -v
```

---

## 🔄 Algoritmo de Agrupación, Consolidación y Control

El sistema rompe el aislamiento tradicional de las transacciones implementando un flujo dinámico de control financiero tripartito:

1.  **Validación de Topes:** Antes de la inserción, el sistema calcula mediante agregaciones de Pandas/SQL si la factura (agrupada por `Categoría`) excede el tope configurado en `DBPresupuestoTope` para el mes en curso.
2.  **Consolidación Dinámica:** Si el sistema registra compras recurrentes con descripciones idénticas de un mismo proveedor, el balance las fusiona sumando linealmente cantidades e impactos financieros totales, aislando las fugas de capital de forma clara.
3.  **Cierre Contable Fijo:** Al cambiar el estado de la factura a `Aceptado`, se inhabilita el borrado y la edición de las entidades correspondientes en la interfaz y en el backend, blindando la integridad de los balances históricos consolidados.