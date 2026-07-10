# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile – AI Interview Coach (Streamlit)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Streamlit config: disable telemetry, set server options
RUN mkdir -p /app/.streamlit
COPY .streamlit/config.toml /app/.streamlit/config.toml 2>/dev/null || true

# Expose Streamlit default port
EXPOSE 8501

# Health-check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the application
ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]
