# Refund Management Agent

FastAPI backend using Groq, LangGraph, Supabase PostgreSQL, Pydantic Settings, and optional LangSmith tracing. The backend records a **simulated refund approval**; it does not transfer money.

## Configure

Copy `.env.example` to `.env` and set `GROQ_API_KEY`, `SUPABASE_URL`, and backend-only `SUPABASE_SECRET_KEY`. Configure `LANGSMITH_API_KEY` only when tracing is enabled. Never expose the Supabase secret key to the React app.

Apply `supabase/migrations/202611180001_orders_and_atomic_refund.sql` to a development Supabase project. It creates orders with RLS enabled, an atomic row-locking RPC, and inserts sample orders only when IDs are absent. Review seed SQL before running against any non-development database.

| Variable | Purpose |
|---|---|
| GROQ_API_KEY | Groq credential |
| GROQ_MODEL | Model name (default `llama-3.3-70b-versatile`) |
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SECRET_KEY | Backend secret key |
| LANGSMITH_API_KEY | Optional trace credential |
| LANGSMITH_PROJECT | LangSmith project |
| LANGSMITH_TRACING | Enable LangSmith tracing |
| REFUND_WINDOW_DAYS | Refund policy window (default 30) |
| FRONTEND_ORIGIN | Allowed frontend origin |

## Run locally

```sh
uv sync
uv run uvicorn app.main:app --reload
```

Swagger UI: `/docs`. Health check: `GET /health`. Chat: `POST /api/v1/chat` with `{"message":"Check order 4521","thread_id":"customer-001"}`.

```sh
uv run pytest
uv run python -m evals.runner
```

The evaluation runner calls Groq using the fixed dataset and scores task completion, tool choice, policy compliance, response accuracy, and tool execution. It uses only in-memory fixture orders and never initializes Supabase, so evaluation refund requests cannot mutate database records. Set `LANGSMITH_TRACING=true` and configure LangSmith credentials to trace evaluation runs. It requires `GROQ_API_KEY` and uses API tokens. Results are written to `evals/results.json`.

Tests requiring real Supabase must use a separate isolated test project and explicitly set `SUPABASE_TEST_URL` and `SUPABASE_TEST_SECRET_KEY`. The integration contract test skips without these values. The local LangGraph MemorySaver preserves thread context only for the lifetime of one process; deploy a durable checkpointer before scaling Cloud Run instances.

## Docker

```sh
docker build -t refund-agent .
docker run --env-file .env -p 8080:8080 refund-agent
```

Cloud Run supplies `PORT`; the container binds to it. Do not copy `.env` into an image.

## API

- `GET /health`: liveness response.
- `POST /api/v1/chat`: accepts a message and client-scoped thread ID; returns answer and thread ID.

Refund eligibility is enforced by the PostgreSQL RPC, not by the model.
