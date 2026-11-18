import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_groq import ChatGroq
from config.database import get_supabase
from config.settings import get_settings
from app.accounts import DEMO_USERS
from app.agents.graph import build_graph
from app.api.routes import router
from app.repositories.order_repository import OrderRepository
from app.services.refund_service import RefundService

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()

    model = ChatGroq(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        temperature=0,
    )
    client = get_supabase()

    # Each account gets its own graph and account-scoped repository.
    app.state.graphs = {}
    for user_name in DEMO_USERS:
        repository = OrderRepository(client, user_name)
        service = RefundService(repository, settings.refund_window_days)
        app.state.graphs[user_name] = build_graph(model, service, user_name)
    yield


app = FastAPI(title="Refund Management Agent", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router)
