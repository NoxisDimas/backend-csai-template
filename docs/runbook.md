Runbook & Troubleshooting

This quick guide (runbook) document is designed for the DevOps and Support teams for incident response in the Customer Service AI system.

1. Real-Time Log Monitoring

Read logs from all replicas:

docker compose logs -f

Read logs specifically for the API component and limit to the last 100 lines:

docker compose logs -f --tail=100 api

Read logs specifically for one worker:

docker logs -f cs_ai_worker_1

2. Common Issue Solutions

❌ HTTP 502 Bad Gateway

Symptoms: The Client/Frontend cannot access the system, receiving a 502 Bad Gateway message.
Root Cause: Nginx lost track of the API container's internal IP address. This usually happens when you restart the API service, causing Docker to change the container's IP dynamically.
Solution: Instruct Nginx to reload the IP cache.

docker compose restart nginx

❌ Timeout reading from redis:6379

Symptoms: There are many errors in the logs regarding redis_listener_failed.
Root Cause: The network connection to Redis frequently drops (idle) or the health_check_interval parameter is too aggressive.
Solution: Ensure the app/core/redis.py file is set with socket_keepalive=True (without health_check_interval). If the code is correct, check the CPU and RAM usage of the Redis container (docker stats).

❌ WebSocket Messages Not Sent / Replies Disconnected (Error 1011)

Symptoms: The chat interface suddenly closes itself when the user sends a message.
Root Cause: Internal error in the Arq queue function (enqueue_job).
Solution:

Ensure the worker service is running: docker compose ps worker.

Check the worker logs to see if the LLM API Key has expired or if Rate Limiting from OpenAI/Google occurred.

❌ Watchtower Fails to Pull New Image

Symptoms: GitHub Actions CI/CD completed successfully, but the server is still running the old version of the app. Watchtower logs (`docker logs watchtower`) show "unauthorized: authentication required".
Root Cause: The GitHub Personal Access Token (PAT) used in `~/.docker/config.json` has expired or was revoked.
Solution: 
1. Generate a new PAT in GitHub with `read:packages` scope.
2. Run `docker login ghcr.io -u <username>` on the server.
3. Restart Watchtower: `docker restart watchtower`.

3. Database Management

Database Recovery (Rollback)

If there is a migration revision that breaks the schema:

docker compose exec api-1 alembic downgrade -1

Check Database Connection (Sanity Check)

Run the built-in connection check script using `uv`:

`docker compose exec api-1 uv run python check_db.py`

Force Wipe Database (For Development Only)

`docker compose exec api-1 uv run python wipe_db.py`

4. Contacting the Infrastructure Team

If the error cannot be resolved within 15 minutes using this runbook, immediately escalate it to the Backend/Infrastructure Engineering team via the internal ticketing system.
