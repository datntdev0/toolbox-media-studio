# Multi-stage build for FastAPI backend
# Stage 1: Build environment
FROM python:3.14-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source required by setuptools
COPY pyproject.toml README.md ./
COPY app/ ./app/

# Install the application and its dependencies into a relocatable prefix
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime environment
FROM python:3.14-slim

WORKDIR /app

# Install runtime system dependencies
# ffmpeg is required for ffmpeg-python package
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed application and dependencies from the builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY shared/ ./shared/

# Create logs directory
RUN mkdir -p logs

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
