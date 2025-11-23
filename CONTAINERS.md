# Container Guide

The EVLA Pipeline provides Docker and Singularity containers for reproducible execution across different environments.

## Table of Contents

- [Docker](#docker)
- [Docker Compose](#docker-compose)
- [Singularity](#singularity)
- [Use Cases](#use-cases)
- [Performance](#performance)

---

## Docker

### Build

```bash
# Build the Docker image
docker build -t evla-pipeline:2.0 .

# Verify build
docker run evla-pipeline:2.0 --version
```

### Run

```bash
# Basic usage (mount current directory)
docker run -v $(pwd):/data evla-pipeline:2.0 /data/observation.asdm

# With polarization calibration
docker run -v $(pwd):/data evla-pipeline:2.0 --polarization /data/observation.asdm

# Disable plots for faster execution
docker run -v $(pwd):/data evla-pipeline:2.0 --disable-plots /data/observation.asdm

# Verbose output
docker run -v $(pwd):/data evla-pipeline:2.0 --verbose /data/observation.asdm

# Interactive shell
docker run -it -v $(pwd):/data evla-pipeline:2.0 bash
```

### Volume Mounts

Mount directories to persist outputs:

```bash
docker run \
  -v $(pwd)/data:/data \
  -v $(pwd)/logs:/data/logs \
  -v $(pwd)/weblog:/data/weblog \
  -v $(pwd)/plots:/data/plots \
  -v $(pwd)/final_caltables:/data/final_caltables \
  evla-pipeline:2.0 /data/observation.asdm
```

### Configuration Files

Use configuration files with containers:

```bash
# Create config on host
evla-pipeline --create-config my_config.yaml

# Edit my_config.yaml with your settings

# Run with config
docker run -v $(pwd):/data evla-pipeline:2.0 \
  --config /data/my_config.yaml /data/observation.asdm
```

---

## Docker Compose

Docker Compose provides simpler command-line usage.

### Setup

```bash
# Build images
docker-compose build

# Verify
docker-compose run pipeline --version
```

### Run

```bash
# Basic run
docker-compose run pipeline observation.asdm

# With options
docker-compose run pipeline --polarization --verbose observation.asdm

# Interactive shell
docker-compose run --rm pipeline-shell
```

### Configuration

Edit `docker-compose.yml` to customize volume mounts and environment variables:

```yaml
services:
  pipeline:
    volumes:
      - ./data:/data
      - ./custom_logs:/data/logs
    environment:
      - EVLA_PIPELINE_LOG_LEVEL=DEBUG
```

---

## Singularity

Singularity is designed for HPC environments where Docker is not allowed.

### Build

```bash
# Build Singularity image (requires sudo)
sudo singularity build evla-pipeline.sif Singularity.def

# Or build without sudo using remote builder
singularity build --remote evla-pipeline.sif Singularity.def
```

### Run

```bash
# Basic usage
singularity run evla-pipeline.sif observation.asdm

# With polarization
singularity run evla-pipeline.sif --polarization observation.asdm

# Bind custom directories
singularity run --bind /scratch/data:/data evla-pipeline.sif /data/observation.asdm

# Interactive shell
singularity shell evla-pipeline.sif
```

### HPC Usage

Example SLURM script:

```bash
#!/bin/bash
#SBATCH --job-name=evla-pipeline
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00

# Set paths
DATA_DIR=/scratch/$USER/vla_data
SINGULARITY_IMAGE=/home/$USER/evla-pipeline.sif

# Run pipeline
singularity run \
  --bind $DATA_DIR:/data \
  $SINGULARITY_IMAGE \
  --verbose /data/observation.asdm

# Outputs will be in $DATA_DIR/logs, $DATA_DIR/weblog, etc.
```

Submit with:
```bash
sbatch run_pipeline.slurm
```

---

## Use Cases

### Development Workflow

```bash
# Build latest code
docker build -t evla-pipeline:dev .

# Test on sample data
docker run -v $(pwd)/test_data:/data evla-pipeline:dev /data/test.asdm

# Interactive debugging
docker run -it -v $(pwd):/pipeline evla-pipeline:dev bash
```

### Production Pipeline

```bash
# Pull stable image (when available from registry)
docker pull nrao/evla-pipeline:2.0

# Run on production data
docker run -v /data/observations:/data nrao/evla-pipeline:2.0 \
  --config /data/production_config.yaml \
  /data/observation_20250123.asdm
```

### Cluster Processing

```bash
# Build Singularity image once
sudo singularity build evla-pipeline.sif Singularity.def

# Copy to cluster
scp evla-pipeline.sif user@cluster:/home/user/

# Submit multiple jobs
for obs in /data/observations/*.asdm; do
  sbatch --export=OBS=$obs run_pipeline.slurm
done
```

---

## Performance

### Resource Recommendations

| Dataset Size | CPU Cores | RAM   | Time  |
|--------------|-----------|-------|-------|
| < 10 GB      | 4         | 16 GB | 2-4h  |
| 10-50 GB     | 8         | 32 GB | 4-8h  |
| 50-100 GB    | 16        | 64 GB | 8-12h |
| > 100 GB     | 32        | 128GB | 12-24h|

### Docker Resource Limits

```bash
# Limit CPU and memory
docker run \
  --cpus=8 \
  --memory=32g \
  -v $(pwd):/data \
  evla-pipeline:2.0 /data/observation.asdm
```

### Optimization Tips

1. **Disable plots** for faster execution:
   ```bash
   docker run -v $(pwd):/data evla-pipeline:2.0 --disable-plots /data/obs.asdm
   ```

2. **Use SSD storage** for measurement sets:
   ```bash
   docker run -v /fast-ssd:/data evla-pipeline:2.0 /data/obs.asdm
   ```

3. **Allocate sufficient memory** (avoid swapping):
   ```bash
   docker run --memory=64g -v $(pwd):/data evla-pipeline:2.0 /data/obs.asdm
   ```

---

## Troubleshooting

### Permission Issues

If you encounter permission errors with Docker:

```bash
# Run with current user ID
docker run --user $(id -u):$(id -g) \
  -v $(pwd):/data evla-pipeline:2.0 /data/obs.asdm
```

### Disk Space

Check Docker disk usage:
```bash
docker system df
docker system prune  # Clean up unused images/containers
```

### CASA Version

Verify CASA version inside container:
```bash
docker run evla-pipeline:2.0 bash -c "python -c 'import casatasks; print(casatasks.__version__)'"
```

---

## Advanced Topics

### Custom Base Image

Modify `Dockerfile` to use different CASA version:

```dockerfile
FROM quay.io/casacore/casa:6.5.0

WORKDIR /pipeline
COPY . /pipeline/
RUN pip install -e .

ENTRYPOINT ["evla-pipeline"]
CMD ["--help"]
```

### Multi-Stage Build

Optimize image size with multi-stage build:

```dockerfile
# Build stage
FROM python:3.10 as builder
WORKDIR /build
COPY . .
RUN pip install --user -e .

# Runtime stage
FROM python:3.10-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENTRYPOINT ["evla-pipeline"]
```

### Registry Deployment

Push to Docker registry:

```bash
# Tag image
docker tag evla-pipeline:2.0 registry.example.com/evla-pipeline:2.0

# Push
docker push registry.example.com/evla-pipeline:2.0

# Pull on other systems
docker pull registry.example.com/evla-pipeline:2.0
```

---

## Quick Reference

```bash
# Docker
docker build -t evla-pipeline:2.0 .
docker run -v $(pwd):/data evla-pipeline:2.0 /data/obs.asdm

# Docker Compose
docker-compose run pipeline obs.asdm

# Singularity
sudo singularity build evla-pipeline.sif Singularity.def
singularity run evla-pipeline.sif obs.asdm

# Interactive
docker run -it -v $(pwd):/data evla-pipeline:2.0 bash
singularity shell evla-pipeline.sif
```

For more information, see the [README](README.md) and [INSTALL](INSTALL.md) guides.
