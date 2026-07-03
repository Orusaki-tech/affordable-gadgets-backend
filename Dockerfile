# Affordable Gadgets Backend - production image
# Uses startup.sh: migrate (with retries) -> collectstatic -> gunicorn

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install runtime deps (Postgres + WeasyPrint native libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Ensure startup.sh is executable
RUN chmod +x startup.sh

# Run as non-root
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Migrate + collectstatic + gunicorn (see startup.sh)
CMD ["./startup.sh"]
