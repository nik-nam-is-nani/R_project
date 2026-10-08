FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including DejaVu unicode fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV DATABASE_URL=sqlite:///./storage/bulk_certificates.db
ENV STORAGE_DIR=./storage

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
