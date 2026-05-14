FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENV PYTHONPATH=/app

CMD ["python", "-m", "streamlit", "run", "app/dashboard/main_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]