FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev curl git && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get install -y ca-certificates && update-ca-certificates

# Increase timeout for uv on slow connections
ENV UV_HTTP_TIMEOUT=300

# Install uv (fast dependency manager)
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install all dependencies (production only)
RUN uv sync --no-dev --frozen

# Copy rest of your app
COPY . .

# Expose Flask/Gunicorn port
EXPOSE 8000

# Run Gunicorn via uv
CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--preload", "main:app"]


