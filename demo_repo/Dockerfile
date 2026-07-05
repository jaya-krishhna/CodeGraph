FROM python:3.11-slim

WORKDIR /app

# Minimal deps for the demo app itself (not the orchestrator/Cognee side).
RUN pip install --no-cache-dir fastapi pydantic

COPY . .

ENV PYTHONPATH=/app

# This app is never actually run as a server for the demo — it exists
# purely as ingestible source for Cognee and a target for pytest.
CMD ["python", "-c", "print('demo_repo is ingest-only; no server to run')"]
