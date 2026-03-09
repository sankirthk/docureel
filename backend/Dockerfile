FROM python:3.13-slim

# Install ffmpeg for video stitching
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .

# Install dependencies with uv
RUN uv pip install --system -e .

# Copy source
COPY . .

# Create local storage directory
RUN mkdir -p local_storage

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
