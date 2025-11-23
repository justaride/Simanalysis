# Simanalysis Docker Image
#
# This Dockerfile creates a production-ready image for running Simanalysis
#
# Build:
#   docker build -t simanalysis:latest .
#
# Run:
#   docker run -v /path/to/mods:/mods simanalysis analyze /mods

FROM python:3.11-slim

LABEL maintainer="justaride" \
      description="Simanalysis - The Sims 4 mod analyzer" \
      version="3.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first (for better caching)
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy test fixtures for demonstration
COPY tests/fixtures/ ./fixtures/

# Create volume mount points
VOLUME ["/mods", "/output"]

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    SIMANALYSIS_LOG_DIR=/output/logs

# Create non-root user for security
RUN useradd -m -u 1000 simuser && \
    chown -R simuser:simuser /app
USER simuser

# Set entrypoint
ENTRYPOINT ["simanalysis"]

# Default command (show help)
CMD ["--help"]

# Usage examples:
#
# Analyze mods:
#   docker run -v /path/to/mods:/mods -v /path/to/output:/output \
#     simanalysis analyze /mods --output /output/report.json
#
# Interactive mode:
#   docker run -it -v /path/to/mods:/mods simanalysis analyze /mods --tui
#
# Shell access:
#   docker run -it --entrypoint /bin/bash simanalysis
#
# With custom log level:
#   docker run -v /path/to/mods:/mods simanalysis analyze /mods --log-level DEBUG
