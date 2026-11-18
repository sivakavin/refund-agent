import logging
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    graph = request.app.state.graphs[payload.user_name]
    scoped_thread_id = f"{payload.user_name}:{payload.thread_id}"

    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=payload.message)]},
            config={"configurable": {"thread_id": scoped_thread_id}},
        )
        answer = result["messages"][-1].content
        if not isinstance(answer, str):
            answer = str(answer)
        return ChatResponse(
            answer=answer,
            thread_id=payload.thread_id,
            user_name=payload.user_name,
        )
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable.")
