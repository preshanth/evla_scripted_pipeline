# EVLA Pipeline Docker Container
#
# This container provides a reproducible environment for running the
# EVLA scripted pipeline with all dependencies pre-installed.
#
# Build:
#   docker build -t evla-pipeline:2.0 .
#
# Run:
#   docker run -v $(pwd):/data evla-pipeline:2.0 /data/your_observation.asdm
#
# Interactive:
#   docker run -it -v $(pwd):/data evla-pipeline:2.0 bash

FROM python:3.10-slim

# Set metadata
LABEL maintainer="NRAO <help@nrao.edu>"
LABEL description="EVLA Scripted Pipeline v2.0 - Automated VLA calibration"
LABEL version="2.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /pipeline

# Copy pipeline code
COPY . /pipeline/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /data
WORKDIR /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV EVLA_PIPELINE_VERSION=2.0.0

# Default command shows help
ENTRYPOINT ["evla-pipeline"]
CMD ["--help"]
