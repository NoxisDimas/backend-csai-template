Deployment Guide

This document guides you through installing, configuring, and deploying the system to a high-scale Production environment.

1. Infrastructure Architecture

graph LR
USER[User / Frontend] -->|HTTPS/WSS| NGINX[Nginx Load Balancer]
NGINX --> API1[API Replica 1]
NGINX --> API2[API Replica 2]
NGINX --> API3[API Replica 3]

    API1 & API2 & API3 -.->|Queue| REDIS[(Redis)]
    REDIS -.-> WORKER1[Worker 1]
    REDIS -.-> WORKER2[Worker 2]

    API1 & API2 & API3 --> DB[(PostgreSQL)]
    WORKER1 & WORKER2 --> DB

    PROM[Prometheus] -.-> NGINX
    PROM -.-> API1 & API2 & API3
    GRAFANA[Grafana] -.-> PROM

2. System Requirements

To run a standard cluster (3 APIs, 3 Workers, Database, Redis, Monitoring), it is recommended:

CPU: Minimum 4 Cores (8 Cores recommended).

RAM: Minimum 8 GB (16 GB if using a local Ollama model).

OS: Ubuntu 22.04 LTS / Debian 12 / Windows Server with WSL2.

Software: Docker Engine version 24+ & Docker Compose v2+.

3. docker-compose.yml Configuration

This system relies heavily on Docker's internal network.
Do not change the service names (e.g., db, redis, api) as they act as internal DNS domains (Service Discovery).

Ensure key variables in .env point to the containers, NOT localhost:

# CORRECT

DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/customer_service_ai
REDIS_URL=redis://redis:6379/0

# INCORRECT

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/customer_service_ai
REDIS_URL=redis://localhost:6379/0

4. Scale-Based Deployment (Scaling)

Instead of a simple docker compose up -d, use the --scale argument to run multiple replicas.

Running the System

docker compose up -d --build --scale api=3 --scale worker=3

[!TIP]
Nginx will automatically detect the 3 api containers and distribute requests using the Round Robin method.

Checking the Status

docker compose ps

Ensure all containers are in an Up status (and Healthy for db and redis).

5. Running Production Migration

After the system is alive for the first time, the database schema is still empty. Run this command from within one of the API replicas:

# SSH into the api-1 container and run Alembic migration

docker compose exec -it api-1 alembic upgrade head

6. Nginx & SSL Certificate Integration

The standard Nginx configuration (nginx/nginx.conf) only supports the HTTP protocol (Port 80). To launch it on a public domain:

Bind your domain to the Server IP.

Install Certbot and request a Let's Encrypt certificate.

Change nginx.conf to listen to port 443 (SSL).

Restart the load balancer: docker compose restart nginx.
