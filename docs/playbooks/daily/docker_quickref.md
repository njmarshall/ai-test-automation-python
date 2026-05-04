# Docker Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Covers containers, images, volumes, networking, Compose, and CI patterns

---

## Table of Contents
- [Installation & Setup](#installation--setup)
- [Images](#images)
- [Containers](#containers)
- [Exec & Logs](#exec--logs)
- [Volumes](#volumes)
- [Networking](#networking)
- [Dockerfile](#dockerfile)
- [Docker Compose](#docker-compose)
- [Registry & Pushing](#registry--pushing)
- [Cleanup](#cleanup)
- [Testing Patterns](#testing-patterns)
- [CI Patterns](#ci-patterns)
- [Gotchas](#gotchas)
- [Quick Reference Card](#quick-reference-card)

---

## Installation & Setup

```bash
# Verify installation
docker --version
docker compose version

# Run hello-world (sanity check)
docker run hello-world

# Login to Docker Hub
docker login

# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# System info
docker info
docker system df                   # disk usage breakdown
```

---

## Images

```bash
# Pull an image
docker pull python:3.11-slim
docker pull node:20-alpine
docker pull openjdk:17-jdk-slim

# List local images
docker images
docker images -a                   # include intermediates
docker images --filter "dangling=true"   # untagged images

# Build an image
docker build -t myapp:latest .
docker build -t myapp:1.0.0 .
docker build -f Dockerfile.test -t myapp-test .
docker build --no-cache -t myapp:latest .      # bypass cache
docker build --build-arg ENV=staging -t myapp .

# Tag an image
docker tag myapp:latest myapp:1.0.0
docker tag myapp:latest ghcr.io/njmarshall/myapp:latest

# Inspect image
docker inspect myapp:latest
docker history myapp:latest         # layer history

# Remove image
docker rmi myapp:latest
docker rmi -f myapp:latest          # force
```

---

## Containers

```bash
# Run a container
docker run python:3.11-slim
docker run -it python:3.11-slim bash            # interactive + TTY
docker run -d nginx:latest                       # detached (background)
docker run --rm python:3.11-slim python -c "print('hi')"  # auto-remove

# Run with options
docker run \
  -d \                                           # detached
  --name my-api \                                # name it
  -p 8080:80 \                                   # port mapping host:container
  -e ENV=staging \                               # env var
  -v $(pwd)/config:/app/config \                 # volume mount
  --network my-network \                         # attach to network
  myapp:latest

# List containers
docker ps                           # running
docker ps -a                        # all (including stopped)
docker ps -q                        # IDs only

# Start / stop / restart
docker start my-api
docker stop my-api
docker restart my-api
docker pause my-api
docker unpause my-api

# Stop all running containers
docker stop $(docker ps -q)

# Remove container
docker rm my-api
docker rm -f my-api                 # force (running container)
docker rm $(docker ps -aq)          # remove all stopped
```

---

## Exec & Logs

```bash
# Execute command in running container
docker exec -it my-api bash
docker exec -it my-api sh           # if bash not available
docker exec my-api python --version
docker exec -e DEBUG=true my-api python manage.py check

# Copy files
docker cp my-api:/app/logs/app.log ./local_logs/
docker cp ./config.yaml my-api:/app/config.yaml

# Logs
docker logs my-api
docker logs -f my-api               # follow (live)
docker logs --tail 100 my-api       # last 100 lines
docker logs --since 1h my-api       # last 1 hour
docker logs my-api 2>&1 | grep ERROR

# Stats (live resource usage)
docker stats
docker stats my-api --no-stream     # one snapshot

# Inspect container
docker inspect my-api
docker inspect my-api --format '{{.NetworkSettings.IPAddress}}'
docker inspect my-api --format '{{.State.Status}}'
```

---

## Volumes

```bash
# Create named volume
docker volume create test-data

# List volumes
docker volume ls

# Inspect volume
docker volume inspect test-data

# Mount volume in run
docker run -v test-data:/app/data myapp:latest

# Bind mount (local directory)
docker run -v $(pwd)/tests:/app/tests myapp:latest
docker run -v $(pwd)/reports:/app/reports myapp:latest    # capture test output

# Read-only mount
docker run -v $(pwd)/config:/app/config:ro myapp:latest

# Remove volume
docker volume rm test-data
docker volume prune                 # remove all unused volumes
```

---

## Networking

```bash
# Create network
docker network create my-network
docker network create --driver bridge test-network

# List networks
docker network ls

# Inspect network
docker network inspect my-network

# Connect container to network
docker network connect my-network my-api
docker network disconnect my-network my-api

# Run container on network
docker run --network my-network --name db postgres:15

# Containers on same network communicate by name
# e.g. from app container: curl http://db:5432

# Remove network
docker network rm my-network
docker network prune               # remove all unused

# Host networking (container shares host network)
docker run --network host myapp:latest
```

---

## Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# ---- Base stage ----
FROM python:3.11-slim AS base
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencies stage ----
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Test stage ----
FROM deps AS test
COPY . .
RUN pytest tests/ --tb=short

# ---- Production stage ----
FROM deps AS prod
COPY src/ ./src/
EXPOSE 8080
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Dockerfile best practices

```dockerfile
# Use specific tags, not latest
FROM python:3.11.9-slim

# Combine RUN commands to minimize layers
RUN apt-get update \
    && apt-get install -y curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .                            # this layer busts less often

# Use non-root user
RUN useradd -m appuser
USER appuser

# .dockerignore
# __pycache__/
# *.pyc
# .git/
# .env
# node_modules/
# build/
```

---

## Docker Compose

### `docker-compose.yml`

```yaml
version: '3.9'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: prod
    image: myapp:latest
    container_name: my-api
    ports:
      - "8080:8080"
    environment:
      - ENV=staging
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
    env_file:
      - .env.local
    volumes:
      - ./config:/app/config:ro
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    container_name: my-db
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d mydb"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  test:
    build:
      context: .
      target: test
    environment:
      - BASE_URL=http://api:8080
    volumes:
      - ./reports:/app/reports
    depends_on:
      - api
    networks:
      - app-network

volumes:
  db-data:

networks:
  app-network:
    driver: bridge
```

### Compose commands

```bash
# Start services
docker compose up
docker compose up -d                            # detached
docker compose up --build                       # rebuild images
docker compose up api db                        # specific services

# Stop services
docker compose down
docker compose down -v                          # also remove volumes
docker compose down --rmi all                   # also remove images

# Manage services
docker compose start api
docker compose stop api
docker compose restart api
docker compose ps                               # status
docker compose logs -f api                      # follow logs
docker compose exec api bash                    # shell into service

# Run one-off command
docker compose run --rm test pytest -m smoke
docker compose run --rm api python manage.py migrate

# Scale
docker compose up --scale api=3

# Config validation
docker compose config                           # validate + show merged config
```

---

## Registry & Pushing

```bash
# Tag for Docker Hub
docker tag myapp:latest njmarshall/myapp:latest
docker tag myapp:latest njmarshall/myapp:1.0.0

# Push to Docker Hub
docker push njmarshall/myapp:latest
docker push njmarshall/myapp:1.0.0

# Tag for GitHub Container Registry (ghcr.io)
docker tag myapp:latest ghcr.io/njmarshall/myapp:latest
docker push ghcr.io/njmarshall/myapp:latest

# Pull from private registry
docker pull ghcr.io/njmarshall/myapp:latest

# Save image to tar (air-gapped environments)
docker save myapp:latest | gzip > myapp.tar.gz
docker load < myapp.tar.gz
```

---

## Cleanup

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune
docker image prune -a               # all unused (not just dangling)

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Nuclear option — remove everything unused
docker system prune
docker system prune -a              # also remove unused images
docker system prune -a --volumes    # also remove volumes

# Check disk usage before cleaning
docker system df
docker system df -v                 # verbose breakdown
```

---

## Testing Patterns

### Run tests in Docker

```bash
# One-shot test run, auto-remove container
docker run --rm \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/reports:/app/reports \
  -e BASE_URL=https://hapi.fhir.org/baseR4 \
  myapp-test:latest \
  pytest tests/ -m smoke --html=reports/report.html

# Run Playwright tests with browsers pre-installed
docker run --rm \
  -v $(pwd):/app \
  -w /app \
  mcr.microsoft.com/playwright/python:v1.43.0-jammy \
  pytest tests/ui/ --browser chromium
```

### Official Playwright Docker image

```bash
# Python
docker pull mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Java
docker pull mcr.microsoft.com/playwright/java:v1.43.0-jammy

# Node.js
docker pull mcr.microsoft.com/playwright:v1.43.0-jammy

# Run Python Playwright tests
docker run --rm \
  -v $(pwd):/app \
  -w /app \
  mcr.microsoft.com/playwright/python:v1.43.0-jammy \
  bash -c "pip install -r requirements.txt && pytest tests/ui/"
```

### Test service with Docker Compose

```bash
# Spin up API + DB, run tests, tear down
docker compose up -d api db
docker compose run --rm test pytest -m regression
docker compose down -v
```

### Capture test artifacts

```bash
docker run --rm \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/screenshots:/app/screenshots \
  myapp-test:latest \
  pytest tests/ --screenshot=only-on-failure --html=reports/report.html
```

---

## CI Patterns

### GitHub Actions with Docker

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Build test image
        run: docker build -t myapp-test --target test .

      - name: Run tests
        run: |
          docker run --rm \
            --network host \
            -e BASE_URL=http://localhost:8080 \
            -v ${{ github.workspace }}/reports:/app/reports \
            myapp-test:latest \
            pytest tests/ -m smoke

      - name: Upload reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-reports
          path: reports/
```

### Docker layer caching in CI

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build with cache
  uses: docker/build-push-action@v5
  with:
    context: .
    push: false
    tags: myapp-test:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
    target: test
```

---

## Gotchas

### Container networking — localhost isn't localhost

```bash
# WRONG — from inside a container, localhost = the container
BASE_URL=http://localhost:8080    # won't reach host machine

# RIGHT — use host.docker.internal (Mac/Windows)
BASE_URL=http://host.docker.internal:8080

# RIGHT — use service name inside compose network
BASE_URL=http://api:8080

# RIGHT — use --network host (Linux only)
docker run --network host myapp-test:latest
```

### Layer cache invalidation

```dockerfile
# WRONG — changing any source file busts requirements install
COPY . .
RUN pip install -r requirements.txt

# RIGHT — copy requirements first
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

### Volume permissions

```bash
# If tests write reports and container runs as non-root:
# Create the directory first so Docker doesn't create it as root
mkdir -p reports
chmod 777 reports                  # or match UID inside container
docker run -v $(pwd)/reports:/app/reports myapp-test
```

### `docker compose` vs `docker-compose`

```bash
# docker-compose (v1) — Python, being deprecated
docker-compose up

# docker compose (v2) — Go plugin, current
docker compose up
```

---

## Quick Reference Card

| Command | Purpose |
|---|---|
| `docker build -t name:tag .` | Build image from Dockerfile |
| `docker run --rm -it image bash` | Interactive container, auto-remove |
| `docker run -d -p 8080:80 image` | Detached with port mapping |
| `docker exec -it name bash` | Shell into running container |
| `docker logs -f name` | Follow live logs |
| `docker ps -a` | All containers including stopped |
| `docker stop $(docker ps -q)` | Stop all running containers |
| `docker system prune -a` | Clean all unused resources |
| `docker compose up -d --build` | Start all services, rebuild |
| `docker compose run --rm svc cmd` | One-off command in service |
| `docker compose down -v` | Stop + remove volumes |
| `docker inspect name` | Full container metadata |
| `docker stats` | Live CPU/memory usage |
| `docker system df` | Disk usage breakdown |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) daily playbooks*
