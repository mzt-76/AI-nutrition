FROM python:3.11-slim

# System deps: gcc/g++ for C extensions, libopenblas for scipy MILP, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libopenblas-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

# Dependencies first (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code — only what the backend needs
COPY src/ ./src/
COPY skills/ ./skills/

# Ownership
RUN chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 8001

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8001"]
