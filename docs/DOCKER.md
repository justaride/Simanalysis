# Docker Guide for Simanalysis

This guide shows you how to use Simanalysis with Docker, eliminating the need for local Python installation.

## Quick Start

### Option 1: Using Docker Run

```bash
# Analyze your mods
docker run -v /path/to/mods:/mods simanalysis:latest analyze /mods

# Export to JSON
docker run -v /path/to/mods:/mods -v $(pwd)/output:/output \
  simanalysis:latest analyze /mods --output /output/report.json
```

### Option 2: Using Docker Compose

```bash
# Set your mods directory
export MODS_DIR=~/Documents/"Electronic Arts"/"The Sims 4"/Mods
export OUTPUT_DIR=$(pwd)/output

# Build the image
docker-compose build

# Run analysis
docker-compose run simanalysis analyze /mods --output /output/report.json
```

## Installation

### 1. Build the Image

#### From Docker Hub (coming soon)

```bash
docker pull simanalysis:latest
```

#### From Source

```bash
# Clone the repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Build the image
docker build -t simanalysis:latest .
```

### 2. Verify Installation

```bash
docker run simanalysis:latest --version
```

Expected output:
```
Simanalysis version 3.0.0
```

## Usage Examples

### Basic Analysis

Analyze a directory of mods:

```bash
docker run -v /path/to/mods:/mods simanalysis:latest analyze /mods
```

**Explanation:**
- `-v /path/to/mods:/mods` - Mount your Mods folder as `/mods` inside the container
- `analyze /mods` - Analyze the mounted directory

### Export Results

Export analysis to JSON:

```bash
docker run \
  -v /path/to/mods:/mods:ro \
  -v $(pwd)/output:/output \
  simanalysis:latest \
  analyze /mods --output /output/report.json --format json
```

**Explanation:**
- `:ro` - Mount as read-only for safety
- `$(pwd)/output:/output` - Mount output directory
- `--format json` - Export as JSON

### Interactive TUI Mode

```bash
docker run -it \
  -v /path/to/mods:/mods:ro \
  simanalysis:latest \
  analyze /mods --tui
```

**Explanation:**
- `-it` - Interactive terminal mode
- `--tui` - Launch text UI interface

### Debug Mode

```bash
docker run \
  -v /path/to/mods:/mods:ro \
  -v $(pwd)/logs:/output/logs \
  simanalysis:latest \
  analyze /mods --log-level DEBUG --log-file /output/logs/debug.log
```

View logs:
```bash
cat logs/debug.log
```

## Docker Compose Usage

### Setup

Create a `.env` file in the project root:

```bash
# .env
MODS_DIR=/home/user/Documents/Electronic Arts/The Sims 4/Mods
OUTPUT_DIR=./output
```

Or export environment variables:

```bash
export MODS_DIR=/path/to/your/mods
export OUTPUT_DIR=$(pwd)/output
```

### Common Commands

**Build the image:**
```bash
docker-compose build
```

**Run analysis:**
```bash
docker-compose run simanalysis analyze /mods
```

**Export to multiple formats:**
```bash
# JSON
docker-compose run simanalysis analyze /mods --output /output/report.json

# TXT
docker-compose run simanalysis analyze /mods --output /output/report.txt

# YAML
docker-compose run simanalysis analyze /mods --output /output/report.yaml
```

**Interactive mode:**
```bash
docker-compose run simanalysis analyze /mods --tui
```

**Development mode:**
```bash
docker-compose run dev
# Now you're in a shell inside the container
# Run tests:
pytest
# Or run simanalysis directly:
simanalysis analyze /mods
```

## Volume Mounts

### Recommended Mount Points

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `/path/to/mods` | `/mods` | Your Sims 4 Mods folder (read-only recommended) |
| `./output` | `/output` | Analysis reports and logs |
| `./fixtures` | `/fixtures` | Test fixtures (optional) |

### Examples

**Mount as read-only (recommended for safety):**
```bash
docker run -v /path/to/mods:/mods:ro simanalysis:latest analyze /mods
```

**Mount multiple directories:**
```bash
docker run \
  -v ~/mods:/mods:ro \
  -v ~/CC:/cc:ro \
  simanalysis:latest \
  analyze /mods /cc
```

## Environment Variables

### Available Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMANALYSIS_LOG_DIR` | `/output/logs` | Directory for log files |
| `PYTHONUNBUFFERED` | `1` | Unbuffered Python output |

### Setting Environment Variables

**With docker run:**
```bash
docker run \
  -e SIMANALYSIS_LOG_DIR=/custom/logs \
  -v /path/to/mods:/mods \
  simanalysis:latest analyze /mods
```

**With docker-compose:**
```yaml
# docker-compose.yml
services:
  simanalysis:
    environment:
      - SIMANALYSIS_LOG_DIR=/custom/logs
```

## Advanced Usage

### Custom Entrypoint

Run a shell instead of simanalysis:

```bash
docker run -it --entrypoint /bin/bash simanalysis:latest
```

### Run Python Scripts

```bash
docker run -v $(pwd)/examples:/examples \
  simanalysis:latest \
  python /examples/basic_usage.py
```

### Mount Source Code for Development

```bash
docker run -it \
  -v $(pwd)/src:/app/src \
  -v /path/to/mods:/mods \
  simanalysis:latest \
  analyze /mods
```

### Run Tests Inside Container

```bash
docker run -it --entrypoint pytest simanalysis:latest
```

Or with docker-compose:
```bash
docker-compose run dev pytest -v
```

## Troubleshooting

### Permission Issues

If you get permission errors accessing mounted volumes:

```bash
# Get your user ID
id -u

# Run with matching user ID
docker run --user $(id -u):$(id -g) \
  -v /path/to/mods:/mods \
  simanalysis:latest analyze /mods
```

### Container Exits Immediately

The default command shows help and exits. To run analysis:

```bash
# Wrong (exits with help)
docker run simanalysis:latest

# Correct (runs analysis)
docker run -v /path/to/mods:/mods simanalysis:latest analyze /mods
```

### Cannot Find Mods

Verify volume mount:

```bash
docker run -v /path/to/mods:/mods \
  --entrypoint ls \
  simanalysis:latest -la /mods
```

### Out of Memory

Increase Docker memory limit:

```bash
# Run with more memory
docker run -m 2g -v /path/to/mods:/mods \
  simanalysis:latest analyze /mods
```

### Logs Not Appearing

Ensure output directory is mounted and writable:

```bash
mkdir -p output/logs
chmod 777 output/logs

docker run \
  -v /path/to/mods:/mods:ro \
  -v $(pwd)/output:/output \
  simanalysis:latest \
  analyze /mods --log-file /output/logs/analysis.log
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/analyze-mods.yml
name: Analyze Mods

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: docker build -t simanalysis:latest .

      - name: Run analysis
        run: |
          docker run \
            -v ${{ github.workspace }}/mods:/mods:ro \
            -v ${{ github.workspace }}/output:/output \
            simanalysis:latest \
            analyze /mods --output /output/report.json

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: analysis-report
          path: output/report.json
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - analyze

analyze-mods:
  stage: analyze
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t simanalysis:latest .
    - docker run -v $(pwd)/mods:/mods:ro -v $(pwd)/output:/output simanalysis:latest analyze /mods --output /output/report.json
  artifacts:
    paths:
      - output/report.json
```

## Best Practices

### 1. Use Read-Only Mounts

Protect your mods from accidental modification:

```bash
docker run -v /path/to/mods:/mods:ro simanalysis:latest analyze /mods
```

### 2. Keep Images Updated

Rebuild regularly to get latest fixes:

```bash
docker-compose build --no-cache
```

### 3. Clean Up Old Containers

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune
```

### 4. Use Named Volumes for Logs

```bash
docker volume create simanalysis-logs

docker run \
  -v /path/to/mods:/mods:ro \
  -v simanalysis-logs:/output/logs \
  simanalysis:latest analyze /mods
```

### 5. Tag Your Images

```bash
docker build -t simanalysis:3.0.0 .
docker tag simanalysis:3.0.0 simanalysis:latest
```

## Platform-Specific Notes

### Windows

Use Windows-style paths:

```powershell
# PowerShell
docker run -v C:\Users\YourName\Documents\"Electronic Arts"\"The Sims 4"\Mods:/mods simanalysis:latest analyze /mods
```

Or with WSL2:

```bash
docker run -v /mnt/c/Users/YourName/Documents/Electronic\ Arts/The\ Sims\ 4/Mods:/mods simanalysis:latest analyze /mods
```

### macOS

Ensure Docker has access to your Documents folder in Docker Desktop preferences.

### Linux

No special configuration needed.

## Performance Tips

1. **Use bind mounts** instead of volumes for better performance with large mod collections
2. **Allocate more memory** if analyzing 1000+ mods: `-m 4g`
3. **Use multi-stage builds** for smaller images (already configured in Dockerfile)
4. **Cache dependencies** by not changing pyproject.toml frequently

## Security Considerations

1. **Run as non-root user** (already configured in Dockerfile)
2. **Use read-only mounts** for mod directories
3. **Don't expose ports** unless necessary
4. **Scan images** regularly: `docker scan simanalysis:latest`
5. **Keep base image updated**: Rebuild when python:3.11-slim updates

## Getting Help

- **Docker Issues**: Check [Docker Documentation](https://docs.docker.com/)
- **Simanalysis Issues**: [GitHub Issues](https://github.com/justaride/Simanalysis/issues)
- **General Help**: See main [README.md](../README.md)

## Next Steps

- Try the [Quick Start Guide](../docs/getting-started/quick-start.md)
- Read [Usage Examples](../USAGE_EXAMPLES.md)
- Explore [Python API](../docs/api/overview.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23 | **License**: MIT
