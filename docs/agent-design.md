Agent Design

This document explains the AI Agent architecture design that powers the Customer Service Backend. We use the LangGraph framework to define the conversational logic flow (state machine) and external calls.

1. State Machine Architecture (LangGraph)

AI logic is represented in a directed graph. Nodes in the graph represent agents or tools, while edges represent decision-making routes.

graph TD
START((START)) --> ROUTER[Router Node]
ROUTER -->|General Questions| FAQ[FAQ/Knowledge Base]
ROUTER -->|Check Stock/Product| SHOPIFY[Shopify API]
ROUTER -->|Heavy/Angry Complaints| ESCALATE[Escalate Node]

    FAQ --> REPLY[Generate Reply]
    SHOPIFY --> REPLY

    REPLY --> END((END))
    ESCALATE --> END

Node Explanations

Router Node: Analyzes the customer's intent. It acts as the main brain distributing tasks to specific nodes.

FAQ/Knowledge Base Node: Performs a vector search (semantic search) to the PostgreSQL database (pgvector) to find return policies, opening hours, etc.

Shopify Node: Connects with the Shopify GraphQL API to fetch product catalog data, stock availability, sizes, and track orders.

Escalate Node: Triggered when the Router detects the customer using abusive language, repeatedly failing to be understood, or explicitly requesting a human agent. This node breaks the AI flow and triggers the Telegram integration.

3. Multi-LLM Fallback Logic

The Customer Service system must be available 24/7 and fault-tolerant to network failures or rate-limiting from AI providers. For this, we designed a tiered fallback system:

Primary: OpenRouter
Provides access to multiple state-of-the-art models (e.g., Llama 3) with high speed, strong reasoning, and reliable token/cost tracking.

Local Fallback: Ollama
If all internet connections are lost or the primary API service is down, the system will switch to using a local Ollama server to ensure basic operations keep running.

This flow is configured via the .env environment variable:

LLM_PRIORITY_LIST=["openrouter", "ollama"]

3. Persistent Memory & Checkpointing

Every conversation has a conversation_id.
We use LangGraph's built-in AsyncPostgresSaver to save the user's historical state directly into PostgreSQL. This ensures:

If the server restarts, the customer conversation context is not lost.

Each new message will be inserted into the last known state without the need to manually resend dozens of old messages into the prompt.
