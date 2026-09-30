# AI Expense Analyzer

An application to keep track of a company's expenses. Upload a PDF invoice or a photo, and the AI reads it, assigns an accounting category to each line item, and shows it all in a dashboard with charts and budget alerts.

---

## Features

- **Invoice reading**: the app extracts vendor, date, and items using the Groq API (vision model `qwen/qwen3.8-27b` and text model `openai/gpt-oss-120b`). If a PDF has no extractable text, it automatically falls back to vision processing.
- **Accounting classification**: each item is tagged with one of these 9 categories:

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

  Classification runs in batches to save tokens, using `openai/gpt-oss-120b` with forced JSON responses.
- **Dashboard (Streamlit + Plotly)**: monthly expense trends, expenses by category, share by vendor, quick metrics, and multi-sheet Excel export.
- **Budget control**: monthly caps per category. If you go over the limit, the category turns red.
- **Admin mode**: add `?admin=1` to the URL to swap AI models on the fly, delete individual invoices, and see every user's invoices.
- **Demo data**: on first launch it seeds 7 sample invoices (AWS, Slack, Meta Ads, Dell, consulting, travel, and education) with dates spread across several months, so you can explore the dashboard without uploading anything. Demo rows do not count against the real invoice limit.

---

## Tech stack

| Tool | Purpose |
|------|---------|
| **Streamlit + Plotly** | Dashboard and charts |
| **Groq API** | AI extraction and classification |
| **openpyxl** | Excel export |
| **SQLite / PostgreSQL** | Database depending on the environment |
| **Docker Compose** | Production environment orchestration |

---

## Project structure

```
expense-analyzer/
├── expense_analyzer/          # Main package
│   ├── ai/                    # Groq communication (extractor, classifier)
│   ├── database/              # ORM models and DB connection
│   └── dashboard/             # Orchestrator, views, services, and styles
├── data/                      # Local SQLite DB (auto-generated, not versioned)
├── docker/                    # Production Dockerfile
├── tests/                     # Unit tests with pytest
├── streamlit_app.py           # Streamlit entry point
├── main.py                    # CLI entry point
├── docker-compose.yml         # PostgreSQL + app orchestration
└── .env.example               # Environment variable template
```

---

## Getting started

### With Docker

1. **Requirements**: Docker and Docker Compose, plus a [Groq Cloud](https://groq.com) API key.
2. **Environment variables**: create a `.env` file in the project root with at least:

   ```ini
   GROQ_API_KEY=your_groq_key
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=invoice_engine_db
   DATABASE_URL=postgresql://admin:secret@db:5432/invoice_engine_db
   ```

3. **Start the app**:

   ```bash
   docker compose up -d --build
   ```

   The app will be at `http://localhost:8501`.

### Locally (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill in `GROQ_API_KEY`, and run:

```bash
streamlit run streamlit_app.py
```

It uses SQLite by default. If you want PostgreSQL, set `DATABASE_URL` in your `.env`.

---

## Data model

The relational model has three tables:

- **DBPresupuestoTope**: monthly limits per category.
- **DBGasto**: invoice header (vendor, date, total, voucher number, demo flag).
- **DBGastoItem**: line items for each invoice (description, quantity, price, category).

```
[DBPresupuestoTope]      [DBGasto] ── (1:N) ──► [DBGastoItem]
```

Money is stored as `Numeric(15,2)` and all math runs on `Decimal` (`ROUND_HALF_UP`) to avoid floating-point errors.

---

## Workflow

1. **You upload** a PDF or image from the dashboard.
2. **The AI extracts** structured data (vendor, date, items).
3. **The AI classifies** each item into a category.
4. **You review and confirm** before saving.
5. **It gets saved** to the database and the charts update instantly.
6. **The system checks** budget caps and alerts you if needed.
7. **It is recorded** in the balance as history. The admin can delete invoices from the dashboard.

---

## Technical notes

- **Financial precision**: everything uses `Decimal` instead of `float` so rounding errors don't pile up.
- **Traceability**: every saved invoice keeps its voucher number, date, and line-item detail in the database.
- **Duplicate protection**: every file is hashed with SHA-256; re-uploading the same invoice is caught automatically.
- **API cost control**: per-user invoice limit (default 5, configurable via `MAX_INVOICES_PER_USER`). Admin mode has no limit and demo rows do not use up quota.
- **File validation**: PDF, PNG, JPG, and JPEG up to 10 MB are accepted; PDFs over 25 pages are rejected before spending tokens.
- **Per-user isolation**: each browser session gets a unique ID (`?uid=...`) and data is scoped per user.
- **SQLite in dev, PostgreSQL in prod**: the system picks the database based on the config.

---

## Tests

```bash
.venv\Scripts\python.exe -m pytest tests -q     # Windows
python -m pytest tests -q                       # Linux/macOS
docker compose exec app pytest tests/unit -v    # inside Docker
```

Tests cover financial precision and rounding, expense consolidation, ORM models and schema migration, data extraction and sanitization, category classification, demo seeding, the invoice limit, and voucher-number uniqueness.

---

## License

Internal use. Personal project for business financial management.

---

Prefer Spanish? → [README.md](README.md)