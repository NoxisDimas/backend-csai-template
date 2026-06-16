Customer Service AI Backend 🤖🛒

An intelligent, AI-powered customer service backend built for Shopify stores. This project utilizes FastAPI, LangGraph, and a multi-LLM fallback architecture to provide real-time, context-aware support to customers via WebSockets. It also integrates seamlessly with Shopify for product search, stock checking, and order lookup.
What is this project?

This is an AI-powered Customer Service backend designed specifically for Shopify stores. This project utilizes the FastAPI framework, LangGraph, and a multi-LLM fallback architecture to provide real-time and interactive customer support via WebSockets. The system also integrates directly with Shopify to search for products, check stock, and track orders.
Key Features

    🧠 Multi-LLM Agent Architecture (LangGraph): A state-machine based AI agent supporting OpenAI, Google Gemini, Groq, and Ollama (Local).

    🛍️ Deep Shopify Integration: Product search, stock checking, and order tracking directly via the Shopify GraphQL API.

    ⚡ Real-time Communication: Instant chat support using WebSockets and Redis Pub/Sub.

    📚 Retrieval-Augmented Generation (RAG): Knowledge base system using PostgreSQL + pgvector.

    🚨 Human Escalation & Telegram Alerting: Automatic escalation to human agents via Telegram.

    🔐 Secure Memory & Persistence: Secure storage of memory and conversation context.

How to Run

1. Clone Repository & Configuration
   Bash

git clone <repository_url>
cd <repository_folder>
cp .env.example .env

Make sure you configure the .env file with your PostgreSQL credentials, Redis, LLM API Keys (OpenAI/Google/Groq), and Shopify keys. 2. Run via Docker (Recommended)

The large-scale architecture (including Load Balancer, Redis, Database, and Workers) is easiest to run with Docker:
Bash

docker compose up -d --build --scale api=3 --scale worker=3

3. Database Migration

Run this command to build the database schema:
Bash

docker compose exec api alembic upgrade head

Folder Structure
Plaintext

app/
├── api/ # REST API & WebSocket endpoints
├── core/ # App configuration, queue (arq), and redis
├── db/ # Database connection and LangGraph checkpointer
├── models/ # Database schemas (SQLAlchemy)
├── services/ # Core business logic and agent orchestrator
└── tools/ # Tools (Shopify, RAG, Escalation) for the AI
docs/ # Project technical details (Architecture, API, etc.)
nginx/ # Load Balancer
prometheus/ # Metrics monitoring

Brief Architecture

This system is designed for high scalability:

    Nginx acts as a Load Balancer distributing traffic to the FastAPI server cluster.

    WebSockets are managed via Redis Pub/Sub so users can connect to any server without being disconnected.

    Time-consuming AI processes (LangGraph) are executed asynchronously by the Worker (Arq) cluster via Redis Queue.

    PostgreSQL is used for persistent data storage, knowledge vectors (pgvector), and AI memory storage (checkpointer).

Links to Docs

In-depth technical details can be found in the docs/ folder:

**Sistem Utama:**

- [Architecture](docs/architecture.md)
- [API Specification](docs/api-spec.md)
- [Database Schema](docs/database-schema.md)
- [Agent Design](docs/agent-design.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Runbook](docs/runbook.md)

**Spesifikasi Frontend:**

- [API Contract](docs/frontend/api-contract.md)
- [Authentication](docs/frontend/authentication.md)
- [WebSocket Events](docs/frontend/websocket-events.md)
- [Error Codes](docs/frontend/error-codes.md)
- [Permissions](docs/frontend/permissions.md)
- [Pagination](docs/frontend/pagination.md)
- [State Machine](docs/frontend/state-machine.md)
- [Examples](docs/frontend/examples.md)
