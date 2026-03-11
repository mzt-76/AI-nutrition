FROM python:3.11-slim

# System deps for C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r ragpipeline && useradd -r -g ragpipeline ragpipeline

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Make entrypoint executable
RUN chmod +x docker_entrypoint.py

# Data dirs + permissions
RUN mkdir -p /app/Local_Files/data /app/Google_Drive/credentials && \
    chown -R ragpipeline:ragpipeline /app

USER ragpipeline

ENV RAG_PIPELINE_TYPE=local
ENV RUN_MODE=continuous
ENV CHECK_INTERVAL=60
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "docker_entrypoint.py"]
