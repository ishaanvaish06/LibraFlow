# Multi-Stage Production Dockerfile for LibraFlow
FROM python:3.11-slim as base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and tests
COPY libflow/ libflow/
COPY tests/ tests/
COPY scripts/ scripts/
COPY README.md ROADMAP.md ./

# Run test suite during build verification
RUN python -m pytest tests/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "libflow.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
