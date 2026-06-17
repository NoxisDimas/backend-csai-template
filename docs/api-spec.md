# Comprehensive API Specification

AI Customer Service for Shopify Store (Single-Instance)

This document defines the complete RESTful and WebSocket application programming interfaces (APIs) exposed by the backend FastAPI service. These APIs handle inbound chat traffic, admin dashboard authentication, Knowledge Base management, and system configurations.

## General Information

- **Base URL**: `/api/v1`
- **Content-Type**: `application/json` (unless specified otherwise, e.g., multipart file uploads)
- **Dashboard Authentication**: Handled via HTTP header: `Authorization: Bearer <JWT_TOKEN>`.
- **Webhook Authentication**: Validated using SHA256 HMAC verification against the Shopify-specific header (`X-Shopify-Hmac-Sha256`).

---

## 1. Authentication & Users (`/auth`)

Endpoints for dashboard access and staff management.

### `POST /auth/login`
Authenticate with email and password. Returns a JWT access token.
- **Request Body**: `{ "email": "admin@store.com", "password": "password123" }`
- **Response**: `{ "success": true, "data": { "access_token": "eyJhbGci..." } }`

### `POST /auth/register`
Create a new dashboard user account. Requires superadmin privileges.
- **Request Body**: `{ "name": "Staff 1", "email": "staff1@store.com", "password": "secure", "role": "admin" }`

### `GET /auth/me`
Get the profile information of the currently authenticated user.

### `PUT /auth/me`
Update the password, email, or name of the currently authenticated user.

---

## 2. Server Health (`/health`)

### `GET /health`
Provides a quick diagnostic to verify that the API server is running and can successfully connect to the PostgreSQL database.
- **Response**: `{ "success": true, "data": { "status": "ok", "database": "healthy", "service": "AI Customer Service Backend" } }`

---

## 3. Chat & Inbound Webhooks (`/webhook`)

### `POST /webhook/shopify`
Receives a new message payload sent by a customer via the Shopify chat widget. This endpoint instantly validates the webhook signature and triggers the LangGraph agentic loop (`create_react_agent`) asynchronously in the background via Arq workers.
- **Headers**: `X-Shopify-Hmac-Sha256: <hash>`

---

## 4. Conversations & Live Inbox (`/conversations` & `/inbox`)

Endpoints to monitor chats in real-time and control the AI handoff process (Kill-Switch).

### `WS /inbox/stream`
Establishes a persistent WebSocket connection to stream real-time message updates and chat status modifications directly to the Live Inbox dashboard.

### `GET /conversations`
Fetch all conversation threads, ordered by the latest activity.

### `GET /conversations/{conversation_id}/messages`
Fetch the complete chronological message history for a specific conversation thread. Returns full message schemas including `cost` and `token_usage`.

### `GET /conversations/all-history`
**(NEW)** Fetch all message history grouped by conversation ID. Includes `cost` and `token_usage` metrics per message to allow frontend mapping.

### `POST /conversations/{conversation_id}/takeover`
**Kill-Switch ON**: Updates the target conversation status to `human_handling`. This immediately prevents the automated AI agent from processing future inputs on this thread, allowing staff to take over.

### `POST /conversations/{conversation_id}/release`
**Kill-Switch OFF**: Re-activates the AI agent for the specified conversation, changing the status back to `active_ai`. This restores automated message loops utilizing LangGraph persistence.

### `POST /conversations/{conversation_id}/messages`
Dispatches a manual message from a customer service representative. Only valid when the conversation status is set to `human_handling`.
- **Request Body**: `{ "content": "I am checking your order right now." }`

### `POST /conversations/{conversation_id}/feedback`
Submit or update CSAT (Customer Satisfaction) feedback for a conversation.
- **Request Body**: `{ "rating": 5, "feedback_text": "Very helpful!" }`

---

## 5. Tickets Management (`/tickets`)

Endpoints to manage human escalation requests.

### `GET /tickets`
Fetch all escalation tickets. Can be filtered by status.
- **Query Params**: `status` (e.g., `?status=open` or `?status=resolved`)

### `PUT /tickets/{ticket_id}/status`
Update the operational status of an escalation ticket.
- **Request Body**: `{ "status": "resolved" }`

### `PUT /tickets/{ticket_id}/notes`
Update internal staff notes for a specific ticket.
- **Request Body**: `{ "notes": "Customer agreed to receive a replacement item." }`

---

## 6. Products (`/products`)

Endpoints connecting the system to the Shopify catalog for the LLM context.

### `GET /products`
Get a list of all synced Shopify products stored in the local database, including their respective vector embedding statuses.

### `POST /products/sync`
Manually trigger a full product synchronization from Shopify. This fetches all products via the Shopify API, compares MD5 hashes to detect changes, updates the local database, and automatically dispatches background tasks to generate vector embeddings for new or modified products.

---

## 7. Analytics (`/analytics`)

Endpoints dedicated to retrieving aggregated operational statistics.

### `GET /analytics/metrics`
Fetch comprehensive dashboard metrics including total token consumption, **actual running costs** (directly queried from the database `total_cost` aggregations), CSAT average, total conversations, and peak hours distribution density.

### `GET /analytics/errors`
Fetch recent silent backend errors and warnings to provide system observability on the admin dashboard.
- **Query Params**: `limit` (default: 50)

---

## 8. Knowledge Base (`/kb`)

Management routes for RAG (Retrieval-Augmented Generation) document ingestion and semantic search integration powered by pgvector.

### `GET /kb/documents`
List all Knowledge Base documents.

### `GET /kb/documents/{document_id}`
Retrieve the detailed content of a specific Knowledge Base document.

### `POST /kb/documents`
Create a new document manually via direct text input.
- **Request Body**: `{ "title": "Return Policy 2026", "content": "Our return policy window..." }`

### `PUT /kb/documents/{document_id}`
Update the content or title of an existing document.

### `DELETE /kb/documents/{document_id}`
Delete a document and immediately cascade-delete its associated vector chunks.

### `POST /kb/documents/upload`
Upload a physical file (`.pdf`, `.txt`, `.csv`) to be parsed and ingested into the Knowledge Base.
- **Content-Type**: `multipart/form-data`

### `POST /kb/documents/{document_id}/process`
Asynchronously triggers text chunking and generates high-dimensional vector embeddings (via OpenAI) for a specific document, saving the results in pgvector.

### `POST /kb/sync-shopify-store`
Automatically scrape and sync default Shopify store policies (Refund, Privacy, Terms of Service, Shipping) into the Knowledge Base.

---

## 9. Configuration (`/config`)

Allows customization of the agent's behavior and system-wide secrets.

### `GET /config/persona`
Retrieves the current active AI persona, tone of voice, and default out-of-context replies.

### `PUT /config/persona`
Updates the AI agent's System Prompt persona and guardrails.
- **Request Body**: `{ "persona_name": "CS Bestie", "tone_of_voice": "Friendly", "out_of_context_message": "...", "rules": "..." }`

### `GET /config/system`
Retrieves system-wide configurations such as the Shopify Domain and API tokens (encrypted).

### `PUT /config/system`
Updates and securely encrypts system configurations like the Shopify Admin API token.
