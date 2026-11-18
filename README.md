# Refund Management Agent

FastAPI backend using Groq, LangGraph, Supabase PostgreSQL, and Pydantic Settings. Refunds are simulated database approvals; no money is transferred.

## Demo accounts

The sample data is assigned as follows:

| Demo account | Order |
|---|---|
| siva | 4521 — Bluetooth Speaker |
| inba | 7788 — Running Shoes |
| soundhu | 1002 — Phone Cover |

Apply migrations in order to a development Supabase project:

1. `supabase/migrations/202611180001_orders_and_atomic_refund.sql`
2. `supabase/migrations/202611180002_demo_order_accounts.sql`

The second migration adds account ownership and replaces the refund function with an account-scoped version. It does not delete existing orders. Unassigned existing orders won’t appear in demo account lists.

These names are **demo account selectors, not authentication**. Do not use this account-selection pattern to protect real customer data; production must bind the account to a verified login.

## Configure

Copy `.env.example` to `.env`. Set `GROQ_API_KEY`, `SUPABASE_URL`, and backend-only `SUPABASE_SECRET_KEY`. Never send the Supabase secret to the frontend.

| Variable | Purpose |
|---|---|
| GROQ_API_KEY | Groq credential |
| GROQ_MODEL | Model ID, e.g. `openai/gpt-oss-120b` |
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SECRET_KEY | Backend secret key |
| LANGSMITH_API_KEY | Optional tracing credential |
| LANGSMITH_PROJECT | LangSmith project name |
| LANGSMITH_TRACING | Enable tracing |
| REFUND_WINDOW_DAYS | Refund window, default 30 |
| FRONTEND_ORIGIN | Allowed frontend origin |

## Run

```sh
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```

Swagger UI is at `/docs`. Chat endpoint: `POST /api/v1/chat`.

Example request:

```json
{"message":"List my orders","thread_id":"chat-1","user_name":"siva"}
```

Use `siva`, `inba`, or `soundhu`. Older requests without `user_name` default to `siva`. Each user's tools are bound to that account before the graph runs, so the model cannot pass a different name to a tool.

## How tool calling is wired

`build_refund_tools` defines the three LangChain tools. `build_graph` registers them in a LangGraph `ToolNode`. The assistant node routes tool requests to that node; after execution, the graph returns the result to the assistant.

- `list_orders`: lists the current demo account's orders.
- `lookup_order`: returns an account's order details and backend eligibility.
- `issue_refund`: records a simulated approval through the atomic SQL function.

The evaluation runner uses in-memory fixtures and does not connect to Supabase. It requires a Groq API key and writes scores to `evals/results.json`.

The app uses an in-memory LangGraph checkpointer. Conversation state is lost when the process restarts.
