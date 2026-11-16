# Own your bambu Cloud - Open Source Dockerfile
# Lightweight Python 3.11 with ffmpeg for timelapse cloud video logo processing.
# Author: Ryan Ben Hassine (https://ryanbenhassine.com)
# License: https://ryanbenhassine.com
# Copyright (c) 2026 Ryan Ben Hassine. All rights reserved.

FROM python:3.11-slim

# Install system dependencies (ffmpeg for video logo compositing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and static assets
COPY app/ /app/app/
COPY static/ /app/static/

# Environment
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 9930

# Start Uvicorn Server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9930"]
