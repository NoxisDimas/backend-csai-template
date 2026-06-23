Backend Architecture & System Design

AI Customer Service for Shopify Store (Single-Instance)

This document explains the high-level architecture (HLA), core components, agentic workflow design, and the recommended directory structure for backend development using FastAPI and LangGraph.

1. High-Level Architecture (HLA)

The backend architecture is designed as a modular monolith centered around the API Gateway (FastAPI). This system acts as a bridge between Shopify (via Webhooks), the Admin Interface (Dashboard), and the AI Engine (LangGraph & LLM).

                             [Incoming Shopify Webhook]
                                         │
                                         ▼
                             [API Gateway (FastAPI)]
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               ▼                                                   ▼
     [Middleware Guardrails]                            [Auth & Admin Endpoints]

- Rate Limiting - Dashboard Analytics
- Out-of-Context Filter - Knowledge Base Setup
- Operational Hours Check - Live Inbox (WebSockets)
  │ │
  ▼ ▼
  [Agentic Loop (LangGraph)] <───────────────────────── [Human Interventions]
- Runtime Dynamic Persona - Takeover / Release
- Async Memory Checkpointer (Kill Switch)
  │
  ┌────────┴────────┐
  ▼ ▼
  [@tool Shopify] [@tool RAG DB]

Main Logical Flow

Inbound Webhook: Messages from customers enter through the Shopify Webhook endpoint into FastAPI.

Middleware & Pre-processing: FastAPI validates request Rate Limits and triggers Guardrail check functions (Out-of-Context identification and Operational Hours status).

Agentic Loop: If the checks pass safely, the user input is forwarded to create_react_agent (LangGraph).

Tool Execution: The agent autonomously decides whether to invoke the Shopify API Tool or the RAG Retriever Tool.

Persistence: The conversational state of the graph is automatically captured and saved by AsyncPostgresSaver.

Outbound Response: The generated AI response is dispatched back to the Shopify Admin API to be displayed on the customer's chat widget.

2. Core Components

2.1 API Gateway (FastAPI)

Role: Receives incoming HTTP and WebSocket requests, validates data payloads using Pydantic, manages admin authentication, and routes requests to corresponding services.

Key Features: Native ASGI support yielding high concurrency, and integrated WebSocket connections for driving the Live Inbox.

2.2 Agentic Orchestrator (LangGraph)

Role: The cognitive engine of the AI support system, built on top of langgraph.prebuilt.create_react_agent.

Characteristics: Acts as an orchestration harness managing the underlying LLM model, the dynamic System Prompt (Persona), integrated tools, and the recursive "ReAct" (Reason-Act) decision loop.

2.3 RAG Engine (pgvector)

Role: Powers semantic document retrieval for the Knowledge Base.

Pipeline: Raw texts are split into segments utilizing LangChain's RecursiveCharacterTextSplitter, converted to high-dimensional vectors via an embedding model (e.g., OpenAI text-embedding-3-small), and indexed/searched in PostgreSQL using Cosine Similarity operators.

2.4 Silent Telemetry (Telegram Bot)

Role: Catches global-level FastAPI unhandled exceptions via customized FastAPI Exception Handlers and asynchronously forwards diagnostic payloads directly to the developer's Telegram Bot, preventing raw technical stack traces from leaking to public client HTTP responses.

3. Ideal Folder Structure

To maintain robust code maintainability as the project scales, the backend will implement a lightweight Domain-Driven Design (DDD) architectural pattern adapted specifically for FastAPI.

backend/
├── app/
│ ├── api/ # Presentation Layer (API Routers & WebSockets)
│ │ ├── v1/
│ │ │ ├── endpoints/
│ │ │ │ ├── webhooks.py # Shopify webhook handlers
│ │ │ │ ├── inbox.py # WebSocket feeds & Handoff (Kill Switch) actions
│ │ │ │ ├── analytics.py # Dashboard metrics endpoints
│ │ │ │ └── kb.py # Knowledge Base management routes
│ │ │ └── router.py # Consolidated v1 API router
│ │ └── dependencies.py # Shared API Dependencies (Auth, DB Sessions, Rate Limiters)
│ │
│ ├── core/ # Core Application Infrastructure Configs
│ │ ├── config.py # Pydantic BaseSettings (env variables, API credentials)
│ │ ├── security.py # Passwords hashing, JWT verification, Shopify HMAC validation
│ │ └── exceptions.py # Custom exception definitions & Telegram alerting integrations
│ │
│ ├── db/ # Relational Database Connection Infrastructure
│ │ ├── session.py # asyncpg database engines & SQLAlchemy sessions configs
│ │ ├── checkpointer.py # Setup configurations for LangGraph AsyncPostgresSaver
│ │ └── base_class.py # Base declarative classes for SQLAlchemy ORM models
│ │
│ ├── models/ # Declarative Database ORM Tables
│ │ ├── conversation.py # Database schemas for conversations, messages, and tickets
│ │ ├── config.py # Database schemas for system_configs and persona_settings
│ │ └── knowledge.py # Database schemas for documents and pgvector chunks
│ │
│ ├── schemas/ # Pydantic Schemas (Request/Response payload validation)
│ │ ├── conversation.py # Chat tables validation
│ │ ├── api_payloads.py # General API structures
│ │ └── agent_state.py # TypedDict representations defining Agent State models
│ │
│ ├── services/ # Core Business Logic Layer (Framework-Independent)
│ │ ├── agent_orchestrator.py # create_react_agent & dynamic persona compilation
│ │ ├── handoff_service.py # Standard operations handling Takeover & Release AI statuses
│ │ ├── rag_pipeline.py # Business pipelines logic for text-splitting and embeddings
│ │ └── metrics_service.py # Aggregators computing dashboard analytics (tokens, CSAT)
│ │
│ ├── tools/ # LangChain @tool definitions (Decoupled modules)
│ │ ├── shopify_tools.py # GetOrderDetails, CheckProductInventory tools
│ │ ├── rag_tools.py # SearchKnowledgeBase vector retrievers
│ │ └── guardrails.py # Preprocessing interceptors for Out-of-Context checks
│ │
│ └── main.py # FastAPI Application Entry Point (App Factory pattern)
│
├── tests/ # Testing Suite (Pytest & Pytest-asyncio)
│ ├── api/ # Presentation and routing tests
│ ├── services/ # Isolated service unit tests
│ └── tools/ # Individual tool mock tests
│
├── .env.example # Sample environment configuration template
├── alembic.ini # Alembic migrations system configuration
├── pyproject.toml # Project configuration and dependencies (managed by uv)
├── uv.lock # Locked dependencies for reproducible builds
└── Dockerfile # Production container assembly configuration

5. CI/CD Pipeline & Deployment Strategy

The system is equipped with a modern CI/CD pipeline using **GitHub Actions**, designed to safely ship code from the repository to the production server:

1. **Continuous Integration (CI):** 
   Triggered on every Pull Request or push to the `main` branch. GitHub Actions automatically sets up Python 3.13 and the `uv` package manager, and runs the entire `pytest` suite. If any test fails, the deployment is aborted to protect production stability.
2. **Continuous Deployment (CD):** 
   If tests pass on the `main` branch, the workflow automatically builds a new Docker Image. This image is pushed securely to the **GitHub Container Registry (GHCR)** tagged as `latest`.
3. **Auto-Deployment via Watchtower:** 
   The production server runs a `containrrr/watchtower` container configured with a Personal Access Token (PAT) to access the private GHCR repository. Watchtower polls the registry periodically and automatically pulls the new image and restarts the application seamlessly with zero manual SSH intervention.

4. Data Flow Analysis for the Handoff Feature

Understanding how the backend state transitions between autonomous AI and manual human intervention is critical when dealing with the "Kill Switch" system:

4.1 Pre-execution State Checks (In services/agent_orchestrator.py)

Before passing execution control downstream to the agent.ainvoke() or agent.astream() loops, the orchestrator service Queries the current record state from the database conversations table:

If status == 'human_handling': The agentic loop execution is immediately aborted and bypassed entirely.

If status == 'waiting_human': The system bypasses LLM inference and returns a static conversational placeholder message (e.g., "Our support representative is currently looking into your request. We will get back to you shortly").

4.2 Autonomous Agentic Loop Execution (Status is active_ai)

The orchestrator pulls Persona parameters from the persona_settings database record and compiles them dynamically into the System Prompt.

The conversation_id is passed as the thread_id to retrieve historical conversational memory structures from the PostgreSQL database via the AsyncPostgresSaver Checkpointer.

The LLM analyzes the incoming query. If required, it references and calls tools located under app/tools/.

If the LLM determines that the issue requires human escalation (guided by rules embedded within the System Prompt), the agent invokes a specialized built-in tool: @tool def escalate_to_human().

This tool executes a backend mutation updating the database conversation status to waiting_human and inserts a corresponding entry into the tickets table.

4.3 Manual UI Intervention (In api/v1/endpoints/conversations.py)

When an administrator clicks the Takeover button on the Live Inbox UI, the endpoint triggers a database state transaction updating conversations.status to human_handling.

The WebSocket server broadcasts this change to update client-side views instantly. From this exact timestamp, the orchestrator completely blocks customer inputs from entering the LangGraph execution graph, leaving the thread open only for human replies.
