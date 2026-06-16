# API Contract

This document explains the structure of *Client-Server* interactions via the REST API interface.
This API acts as a management interface for the reporting dashboard and external data synchronization. It is **NOT** intended for real-time chat communication (for real-time chat, please refer to [WebSocket Events](websocket-events.md)).

## 1. General Conventions

All requests and responses that contain a body must use the JSON format (`application/json`).
- **Base API URL**: `https://<domain>/api/v1`

---

## 2. Knowledge Base Synchronization API

Used to embed documents into the Vector Database (PostgreSQL + pgvector).

### `POST /kb/upload`
Receives a physical document file, splits it into chunks, generates embeddings, and saves them.

**Request:**
- `Content-Type`: `multipart/form-data`
- `file`: Physical file (PDF, TXT, CSV).

**Response:** (200 OK)
```json
{
  "message": "Document successfully processed and saved to the Knowledge Base.",
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "chunks_created": 42
}
```

---

## 3. Analytics & Dashboard API

Used to load charts and Customer Service statistics.

### `GET /analytics/overview`
Fetches a summary of overall AI performance metrics data.

**Query Parameters:**
- `start_date` (optional, format `YYYY-MM-DD`)
- `end_date` (optional, format `YYYY-MM-DD`)

**Response:** (200 OK)
```json
{
  "total_tokens": 154200,
  "estimated_cost_usd": 1.25,
  "csat_average": 4.8,
  "total_conversations": 320,
  "total_tickets": 12
}
```

### `GET /analytics/peak-hours`
Gets the distribution of incoming chat volumes per hour for peak-time analysis.

**Response:** (200 OK)
```json
{
  "data": {
    "08:00": 45,
    "09:00": 120,
    "10:00": 80
  }
}
```

---

## 4. External Webhooks

### `POST /webhook/shopify`
A dedicated endpoint automatically called by Shopify when there are inventory changes or new products added.
The backend system captures this event, generates new vectors, and instantly updates the AI's knowledge.

**Request Headers:**
- `X-Shopify-Topic`: Event name (e.g., `products/create`)
- `X-Shopify-Hmac-Sha256`: Security validation hash.

**Response:** (200 OK)
```json
{"status": "success"}
```
